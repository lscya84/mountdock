from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

APPDATA_SCOPE = "https://www.googleapis.com/auth/drive.appdata"
DEFAULT_SCOPES = [
    APPDATA_SCOPE,
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
]


class GoogleAuthError(Exception):
    """Raised when Google OAuth configuration or token handling fails."""


class GoogleAuthManager:
    def __init__(
        self,
        secrets_path: str | Path,
        token_path: str | Path,
        scopes: list[str] | None = None,
    ):
        self.secrets_path = Path(secrets_path)
        self.token_path = Path(token_path)
        self.scopes = scopes or list(DEFAULT_SCOPES)

    def has_client_secrets(self) -> bool:
        return self.secrets_path.exists()

    def load_credentials(self) -> Credentials | None:
        if not self.token_path.exists():
            return None
        try:
            creds = Credentials.from_authorized_user_file(str(self.token_path), self.scopes)
        except Exception as exc:
            raise GoogleAuthError(f"Failed to load Google token: {exc}") from exc
        return creds

    def get_valid_credentials(self, interactive: bool = False) -> Credentials:
        creds = self.load_credentials()
        if creds and creds.valid and self._has_required_scopes(creds):
            return creds

        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                self.save_credentials(creds)
                if self._has_required_scopes(creds):
                    return creds
            except Exception as exc:
                if not interactive:
                    raise GoogleAuthError(f"Failed to refresh Google token: {exc}") from exc

        if not interactive:
            raise GoogleAuthError("Interactive Google sign-in is required")

        return self.run_oauth_flow()

    def run_oauth_flow(self) -> Credentials:
        if not self.has_client_secrets():
            raise GoogleAuthError(f"Google client secrets file not found: {self.secrets_path}")

        try:
            flow = InstalledAppFlow.from_client_secrets_file(str(self.secrets_path), self.scopes)
            creds = flow.run_local_server(port=0)
            self.save_credentials(creds)
            return creds
        except Exception as exc:
            raise GoogleAuthError(f"Google OAuth sign-in failed: {exc}") from exc

    def save_credentials(self, creds: Credentials):
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        self.token_path.write_text(creds.to_json(), encoding="utf-8")

    def clear_credentials(self):
        try:
            self.token_path.unlink(missing_ok=True)
        except Exception as exc:
            raise GoogleAuthError(f"Failed to clear Google token: {exc}") from exc

    def has_cached_credentials(self) -> bool:
        try:
            return self.load_credentials() is not None
        except GoogleAuthError:
            return False

    def get_account_email(self, creds: Credentials | None = None) -> str:
        creds = creds or self.load_credentials()
        if not creds:
            return ""
        data = self._parse_id_token(claim_source=creds)
        return str(data.get("email", "")) if isinstance(data, dict) else ""

    def _parse_id_token(self, claim_source: Credentials) -> Dict[str, Any]:
        id_token = getattr(claim_source, "id_token", None)
        if not id_token:
            return {}

        parts = id_token.split(".")
        if len(parts) < 2:
            return {}

        payload_part = parts[1]
        padding = "=" * (-len(payload_part) % 4)
        try:
            import base64

            decoded = base64.urlsafe_b64decode(payload_part + padding)
            return json.loads(decoded.decode("utf-8"))
        except Exception:
            return {}

    def _has_required_scopes(self, creds: Credentials) -> bool:
        try:
            return creds.has_scopes(self.scopes)
        except Exception:
            return True
