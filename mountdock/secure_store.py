from __future__ import annotations

from typing import Optional

import keyring
from keyring.errors import KeyringError

SERVICE_NAME = "MountDock.GoogleSync"
USERNAME_PREFIX = "google-sync"


class SecureStoreError(Exception):
    """Raised when the local secure credential store fails."""


class SecureStore:
    def __init__(self, service_name: str = SERVICE_NAME):
        self.service_name = service_name

    def save_cached_passphrase(self, account_email: str, secret: str):
        username = self._build_username(account_email)
        try:
            keyring.set_password(self.service_name, username, secret)
        except KeyringError as exc:
            raise SecureStoreError(f"Failed to save passphrase to secure store: {exc}") from exc

    def load_cached_passphrase(self, account_email: str) -> Optional[str]:
        username = self._build_username(account_email)
        try:
            return keyring.get_password(self.service_name, username)
        except KeyringError as exc:
            raise SecureStoreError(f"Failed to load passphrase from secure store: {exc}") from exc

    def clear_cached_passphrase(self, account_email: str):
        username = self._build_username(account_email)
        try:
            keyring.delete_password(self.service_name, username)
        except keyring.errors.PasswordDeleteError:
            return
        except KeyringError as exc:
            raise SecureStoreError(f"Failed to clear passphrase from secure store: {exc}") from exc

    def _build_username(self, account_email: str) -> str:
        normalized = (account_email or "default").strip().lower() or "default"
        return f"{USERNAME_PREFIX}:{normalized}"
