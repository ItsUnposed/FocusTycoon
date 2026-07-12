"""Encrypts portal passwords with AES-256-GCM.

The format matches the reference (Web Crypto):
  - key = the UTF-8 bytes of PORTAL_ENCRYPTION_KEY, padded on the right with '0'
    to 32 bytes and cut to 32 bytes.
  - a 12-byte random IV, AES-GCM, a 128-bit tag (added after the ciphertext).
  - wire format: base64(iv) + ":" + base64(ciphertext+tag).

Needs the 'cryptography' package (see requirements.txt).
"""

from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .portal_exception import DecryptException

_IV_LENGTH = 12
_KEY_BYTES = 32


class CredentialCipher:
    def __init__(self, encryption_key):
        self._key = _derive_key(encryption_key)

    def encrypt(self, plaintext):
        try:
            # A fresh random initialization vector every time: reusing one with the
            # same key would make AES-GCM unsafe.
            initialization_vector = os.urandom(_IV_LENGTH)
            ciphertext = AESGCM(self._key).encrypt(
                initialization_vector, plaintext.encode("utf-8"), None)
            # Wire format from the module docstring: base64(iv) + ":" + base64(ciphertext+tag).
            return (base64.b64encode(initialization_vector).decode("ascii") + ":"
                    + base64.b64encode(ciphertext).decode("ascii"))
        except Exception:
            # Do not put the password or any detail into the message.
            raise RuntimeError("Encryption failed.")

    def decrypt(self, encoded):
        try:
            # Split "base64(iv):base64(ciphertext+tag)" at the separator.
            separator = encoded.index(":")
            initialization_vector = base64.b64decode(encoded[:separator])
            ciphertext = base64.b64decode(encoded[separator + 1:])
            return AESGCM(self._key).decrypt(
                initialization_vector, ciphertext, None).decode("utf-8")
        except Exception:
            raise DecryptException()


def _derive_key(key):
    # Pad on the right with '0' to 32 bytes, then cut to 32 bytes.
    raw = (key or "").encode("utf-8")
    output = bytearray(b"0" * _KEY_BYTES)
    length = min(len(raw), _KEY_BYTES)
    output[0:length] = raw[0:length]
    return bytes(output)
