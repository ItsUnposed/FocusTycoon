"""Runs the sync of a portal.

Load credentials, check the rate limit, decrypt, scrape, upsert, write the sync
metadata. One lock per portal (single-flight), so a manual and a scheduled sync
never overlap. Every error is non-fatal.

Blocking - always run this off the main thread. start_auto_sync also runs a
periodic background sync over all stored portals on a daemon thread.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone

from .credential_store import CredentialStore
from .iserv_client import IServClient
from .logineo_client import LogineoClient
from .model.sync_result import SyncResult
from .portal_exception import (NoCredentialsException, PortalException,
                               PortalScrapeException, RateLimitedException)
from .portal_type import PortalType
from .util import date_utils

_RATE_LIMIT_MINUTES = 30
DEFAULT_AUTO_SYNC_MINUTES = 30


class AutoSyncResult:
    """The result of one auto-sync tick over all stored portals."""

    def __init__(self, imported, skipped, messages):
        self.imported = imported
        self.skipped = skipped
        self.messages = messages

    def has_changes(self):
        return self.imported > 0

    def summarize(self):
        text = f"{self.imported} new, {self.skipped} updated task(s)"
        if self.messages:
            text += " -- " + " | ".join(self.messages)
        return text


class PortalSyncService:
    def __init__(self, store: CredentialStore, cipher, sink, clients):
        self._store = store
        self._cipher = cipher
        self._sink = sink
        self._clients = clients
        # One lock per portal (single-flight).
        self._locks = {portal: threading.Lock() for portal in PortalType}
        self._tick_lock = threading.Lock()
        self._stop_event = None
        self._thread = None

    def sync(self, portal_type, force):
        lock = self._locks[portal_type]
        if not lock.acquire(blocking=False):
            return SyncResult(0, 0, portal_type, "A sync is already running.")
        try:
            return self._do_sync(portal_type, force)
        finally:
            lock.release()

    def _do_sync(self, portal_type, force):
        credential = self._store.find(portal_type)
        if credential is None:
            raise NoCredentialsException()

        # Rate limit (30 minutes between syncs, unless forced).
        if not force and credential.last_sync_at and credential.last_sync_at.strip():
            minutes = _minutes_since(credential.last_sync_at)
            if minutes is not None and minutes < _RATE_LIMIT_MINUTES:
                raise RateLimitedException(max(1, _RATE_LIMIT_MINUTES - int(minutes)))

        # Decrypt.
        try:
            password = self._cipher.decrypt(credential.password_enc)
        except PortalException as error:
            self._store.update_sync_meta(portal_type, credential.last_sync_at, error.user_message)
            raise

        client = self._clients.get(portal_type)
        if client is None:
            error = PortalScrapeException("This portal is not supported yet.")
            self._store.update_sync_meta(portal_type, credential.last_sync_at, error.user_message)
            raise error

        # Scrape.
        try:
            result = client.scrape(credential.school_url, credential.username, password, False)
        except PortalException as error:
            self._store.update_sync_meta(portal_type, credential.last_sync_at, error.user_message)
            raise
        except Exception as error:  # noqa: BLE001 - network / IO error
            wrapped = PortalScrapeException(f"Network error during sync: {error}")
            self._store.update_sync_meta(portal_type, credential.last_sync_at, wrapped.user_message)
            raise wrapped

        # Keep only future (or today's) due dates - portals sometimes return long-past
        # entries, and a to-do board should not show months-old homework.
        today = date_utils.today_berlin()
        upcoming = [task for task in result.tasks if task.due_date >= today]
        past_count = len(result.tasks) - len(upcoming)

        # Upsert (de-duplicate) + update the sync metadata.
        upsert = self._sink.upsert(upcoming)
        self._store.update_sync_meta(portal_type, _now_iso(), None)

        if not upcoming:
            message = "No new tasks found."
        else:
            message = f"{upsert.imported} new, {upsert.skipped} updated task(s)."
        if past_count > 0:
            message += f" ({past_count} past hidden)"
        return SyncResult(upsert.imported, upsert.skipped, portal_type, message)

    # ---------- scheduled background sync ----------

    def sync_all_stored(self, force):
        imported = 0
        skipped = 0
        messages = []
        for portal_type in list(self._store.load_all().keys()):
            try:
                result = self.sync(portal_type, force)
                imported += result.imported
                skipped += result.skipped
                if result.imported > 0 or result.skipped > 0:
                    messages.append(f"{portal_type.display_name}: {result.message}")
            except PortalException as error:
                messages.append(f"{portal_type.display_name}: {error.user_message}")
        return AutoSyncResult(imported, skipped, messages)

    def start_auto_sync(self, interval_minutes, on_result):
        self.stop_auto_sync()
        interval_seconds = max(1, interval_minutes) * 60
        stop_event = threading.Event()
        self._stop_event = stop_event

        def loop():
            while not stop_event.wait(interval_seconds):
                if not self._tick_lock.acquire(blocking=False):
                    continue  # a tick is still running -> skip this one
                try:
                    on_result(self.sync_all_stored(False))
                except Exception as error:  # noqa: BLE001
                    on_result(AutoSyncResult(0, 0, [f"Auto-sync error: {error}"]))
                finally:
                    self._tick_lock.release()

        thread = threading.Thread(target=loop, name="portal-sync", daemon=True)
        self._thread = thread
        thread.start()

    def stop_auto_sync(self):
        if self._stop_event is not None:
            self._stop_event.set()
            self._stop_event = None
            self._thread = None

    def is_auto_sync_running(self):
        return self._thread is not None and self._thread.is_alive()

    def shutdown(self):
        self.stop_auto_sync()


def with_defaults(store, cipher, sink):
    """The default wiring: Logineo + IServ."""
    clients = {
        PortalType.LOGINEO_NRW: LogineoClient(),
        PortalType.ISERV: IServClient(),
    }
    return PortalSyncService(store, cipher, sink, clients)


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _minutes_since(timestamp):
    try:
        normalized = timestamp.replace("Z", "+00:00")
        moment = datetime.fromisoformat(normalized)
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - moment
        return delta.total_seconds() / 60.0
    except ValueError:
        return None  # invalid timestamp -> allow the sync
