"""Stores the (encrypted) portal credentials.

They live in ~/.focustycoon/portal-credentials.json (outside the repo). The
password is only stored in encrypted form and is never written in clear text.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import portal_type as portal_type_module
from .portal_type import PortalType


class Credential:
    def __init__(self, portal_type, username, password_enc, school_url, last_sync_at, sync_error):
        self.portal_type = portal_type
        self.username = username
        self.password_enc = password_enc
        self.school_url = school_url
        self.last_sync_at = last_sync_at
        self.sync_error = sync_error

    def with_sync_meta(self, new_last_sync_at, new_sync_error):
        return Credential(self.portal_type, self.username, self.password_enc, self.school_url,
                          new_last_sync_at, new_sync_error)


class CredentialStore:
    def __init__(self, file=None):
        if file is None:
            file = Path.home() / ".focustycoon" / "portal-credentials.json"
        self.file = file

    def find(self, portal_type):
        return self.load_all().get(portal_type)

    def save(self, credential):
        all_credentials = self.load_all()
        all_credentials[credential.portal_type] = credential
        self._persist(all_credentials)

    def update_sync_meta(self, portal_type, last_sync_at, sync_error):
        all_credentials = self.load_all()
        existing = all_credentials.get(portal_type)
        if existing is not None:
            all_credentials[portal_type] = existing.with_sync_meta(last_sync_at, sync_error)
            self._persist(all_credentials)

    def delete(self, portal_type):
        all_credentials = self.load_all()
        if all_credentials.pop(portal_type, None) is not None:
            self._persist(all_credentials)

    def load_all(self):
        result = {}
        if not self.file.is_file():
            return result
        try:
            root = json.loads(self.file.read_text(encoding="utf-8"))
            entries = root.get("credentials") if isinstance(root, dict) else None
            if isinstance(entries, list):
                for item in entries:
                    if not isinstance(item, dict):
                        continue
                    wire = _read_string(item.get("portalType"))
                    if not wire.strip():
                        continue
                    portal_type = portal_type_module.from_wire(wire)
                    result[portal_type] = Credential(
                        portal_type,
                        _read_string(item.get("username")),
                        _read_string(item.get("passwordEnc")),
                        _read_string(item.get("schoolUrl")),
                        _read_nullable(item.get("lastSyncAt")),
                        _read_nullable(item.get("syncError")))
        except (OSError, ValueError) as error:
            print(f"Portal credentials could not be read ({self.file}): {error}")
        return result

    def _persist(self, all_credentials):
        try:
            self.file.parent.mkdir(parents=True, exist_ok=True)
            data = {"credentials": [{
                "portalType": credential.portal_type.wire,
                "username": credential.username,
                "passwordEnc": credential.password_enc,
                "schoolUrl": credential.school_url,
                "lastSyncAt": credential.last_sync_at,
                "syncError": credential.sync_error,
            } for credential in all_credentials.values()]}
            self.file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError as error:
            raise IOError(f"Portal credentials could not be saved: {self.file}") from error


def _read_string(value):
    return value if isinstance(value, str) else ""


def _read_nullable(value):
    return value if isinstance(value, str) else None
