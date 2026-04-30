from __future__ import annotations

import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mountdock.crypto_utils import decrypt_rclone_conf, encrypt_rclone_conf
from mountdock.google_auth import GoogleAuthError, GoogleAuthManager
from mountdock.google_drive_sync import GoogleDriveSync, GoogleDriveSyncError
from mountdock.secure_store import SecureStore, SecureStoreError


DEFAULT_APPDATA_SUBDIR = Path("rclone") / "rclone.conf"


class SyncServiceError(Exception):
    """Raised when encrypted rclone.conf sync operations fail."""


def get_runtime_app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


class SyncService:
    def __init__(self, config_manager: Any, auth_manager: GoogleAuthManager, secure_store: SecureStore | None = None):
        self.config = config_manager
        self.auth = auth_manager
        self.secure_store = secure_store or SecureStore()

    def sign_in(self, interactive: bool = True):
        try:
            creds = self.auth.get_valid_credentials(interactive=interactive)
        except GoogleAuthError as exc:
            raise SyncServiceError(str(exc)) from exc

        self._update_account_metadata(creds)
        self.config.update_google_sync_state(google_sync_enabled=True)
        return creds

    def sign_out(self):
        account_email = self.config.get("google_account_email", "")
        try:
            self.auth.clear_credentials()
        except GoogleAuthError as exc:
            raise SyncServiceError(str(exc)) from exc
        self.config.clear_google_auth_state()
        if account_email:
            try:
                self.secure_store.clear_cached_passphrase(account_email)
            except SecureStoreError:
                pass

    def has_remote_backup(self, interactive: bool = False) -> bool:
        creds = self._get_credentials(interactive=interactive)
        drive = GoogleDriveSync(creds)
        return drive.find_sync_file(self.config.get_google_sync_file_name()) is not None

    def backup_current_conf(self, passphrase: str, interactive: bool = False) -> dict[str, Any]:
        source = self.get_existing_conf_path()
        if not source.exists():
            raise SyncServiceError(f"rclone.conf not found: {source}")

        plaintext = source.read_bytes()
        payload = encrypt_rclone_conf(plaintext, passphrase, self.config.get_device_id())
        creds = self._get_credentials(interactive=interactive)
        drive = GoogleDriveSync(creds)

        try:
            file_id = drive.upload_payload(payload, self.config.get_google_sync_file_name())
        except GoogleDriveSyncError as exc:
            raise SyncServiceError(str(exc)) from exc

        now = self._utc_now()
        self._update_account_metadata(creds)
        self.config.update_google_sync_state(
            google_sync_enabled=True,
            google_sync_last_uploaded_at=now,
        )
        return {
            "file_id": file_id,
            "uploaded_at": now,
            "source_path": str(source),
        }

    def restore_conf(
        self,
        passphrase: str,
        *,
        overwrite: bool = False,
        interactive: bool = False,
        target_path: str | Path | None = None,
    ) -> dict[str, Any]:
        creds = self._get_credentials(interactive=interactive)
        drive = GoogleDriveSync(creds)
        try:
            payload = drive.download_payload(self.config.get_google_sync_file_name())
        except GoogleDriveSyncError as exc:
            raise SyncServiceError(str(exc)) from exc

        plaintext = decrypt_rclone_conf(payload, passphrase)
        destination = Path(target_path) if target_path else self.get_restore_target_path()
        destination = destination.resolve()

        if destination.exists() and not overwrite:
            backup_path = self._backup_existing_file(destination)
        else:
            backup_path = None

        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(plaintext)

        self.config.update_google_sync_state(
            google_sync_enabled=True,
            google_sync_last_downloaded_at=self._utc_now(),
        )
        self._update_account_metadata(creds)

        relative = os.path.relpath(destination, get_runtime_app_dir())
        self.config.set("rclone_conf_path", relative)

        return {
            "restored_to": str(destination),
            "backup_path": str(backup_path) if backup_path else "",
            "remote_updated_at": str((payload.get("meta") or {}).get("updated_at", "")),
        }

    def get_existing_conf_path(self) -> Path:
        resolved = (self.config.resolve_rclone_conf_path() or "").strip()
        if resolved:
            path = Path(resolved)
            if path.exists():
                return path.resolve()

        discovered = self._find_default_conf_candidates(existing_only=True)
        if discovered:
            return discovered[0]

        return self.get_restore_target_path()

    def get_restore_target_path(self) -> Path:
        managed_path = self.config.get_rclone_conf_store_path()
        if managed_path:
            return Path(managed_path).resolve()

        configured = (self.config.get("rclone_conf_path", "") or "").strip()
        if configured:
            raw = Path(configured)
            if raw.is_absolute():
                return raw
            return (get_runtime_app_dir() / raw).resolve()

        app_dir_candidate = get_runtime_app_dir() / "rclone.conf"
        return app_dir_candidate.resolve()

    def _find_default_conf_candidates(self, existing_only: bool) -> list[Path]:
        app_dir_candidate = get_runtime_app_dir() / "rclone.conf"
        appdata = os.environ.get("APPDATA", "").strip()
        appdata_candidate = Path(appdata) / DEFAULT_APPDATA_SUBDIR if appdata else None
        home_candidate = Path.home() / ".config" / "rclone" / "rclone.conf"
        candidates = [app_dir_candidate, appdata_candidate, home_candidate]
        resolved: list[Path] = []
        for candidate in candidates:
            if not candidate:
                continue
            candidate = candidate.resolve()
            if existing_only and not candidate.exists():
                continue
            if candidate not in resolved:
                resolved.append(candidate)
        return resolved

    def _get_credentials(self, interactive: bool):
        try:
            return self.auth.get_valid_credentials(interactive=interactive)
        except GoogleAuthError as exc:
            raise SyncServiceError(str(exc)) from exc

    def _update_account_metadata(self, creds):
        email = self.auth.get_account_email(creds)
        updates: dict[str, Any] = {}
        if email:
            updates["google_account_email"] = email
        updates["google_sync_file_name"] = self.config.get_google_sync_file_name()
        if updates:
            self.config.update_google_sync_state(**updates)

    def cache_passphrase(self, passphrase: str):
        email = self.config.get("google_account_email", "")
        if not email:
            raise SyncServiceError("Google account email is not available for secure passphrase caching")
        try:
            self.secure_store.save_cached_passphrase(email, passphrase)
        except SecureStoreError as exc:
            raise SyncServiceError(str(exc)) from exc

    def load_cached_passphrase(self) -> str:
        email = self.config.get("google_account_email", "")
        if not email:
            return ""
        try:
            return self.secure_store.load_cached_passphrase(email) or ""
        except SecureStoreError as exc:
            raise SyncServiceError(str(exc)) from exc

    def clear_cached_passphrase(self):
        email = self.config.get("google_account_email", "")
        if not email:
            return
        try:
            self.secure_store.clear_cached_passphrase(email)
        except SecureStoreError as exc:
            raise SyncServiceError(str(exc)) from exc

    def _backup_existing_file(self, path: Path) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = path.with_name(f"{path.name}.bak-{timestamp}")
        shutil.copy2(path, backup_path)
        return backup_path

    def _utc_now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
