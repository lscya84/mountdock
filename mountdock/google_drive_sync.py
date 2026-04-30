from __future__ import annotations

import io
import json
from typing import Any, Dict

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

APPDATA_FOLDER = "appDataFolder"
DEFAULT_FILE_NAME = "mountdock_rclone_conf_v1.json"
MIME_TYPE_JSON = "application/json"


class GoogleDriveSyncError(Exception):
    """Raised when appDataFolder sync actions fail."""


class GoogleDriveSync:
    def __init__(self, credentials):
        self.credentials = credentials
        self._service = None

    @property
    def service(self):
        if self._service is None:
            self._service = build("drive", "v3", credentials=self.credentials, cache_discovery=False)
        return self._service

    def find_sync_file(self, file_name: str = DEFAULT_FILE_NAME) -> Dict[str, Any] | None:
        query = (
            f"name = '{self._escape_query(file_name)}' "
            f"and '{APPDATA_FOLDER}' in parents and trashed = false"
        )
        try:
            response = (
                self.service.files()
                .list(
                    spaces=APPDATA_FOLDER,
                    q=query,
                    pageSize=1,
                    fields="files(id,name,modifiedTime,size)",
                )
                .execute()
            )
        except HttpError as exc:
            raise GoogleDriveSyncError(f"Failed to query Google Drive appDataFolder: {exc}") from exc

        files = response.get("files", [])
        return files[0] if files else None

    def upload_payload(self, payload: Dict[str, Any], file_name: str = DEFAULT_FILE_NAME) -> str:
        payload_bytes = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        stream = io.BytesIO(payload_bytes)
        media = MediaIoBaseUpload(stream, mimetype=MIME_TYPE_JSON, resumable=False)
        existing = self.find_sync_file(file_name)

        try:
            if existing:
                result = (
                    self.service.files()
                    .update(fileId=existing["id"], media_body=media, fields="id")
                    .execute()
                )
            else:
                metadata = {
                    "name": file_name,
                    "parents": [APPDATA_FOLDER],
                    "mimeType": MIME_TYPE_JSON,
                }
                result = (
                    self.service.files()
                    .create(body=metadata, media_body=media, fields="id")
                    .execute()
                )
        except HttpError as exc:
            raise GoogleDriveSyncError(f"Failed to upload encrypted payload: {exc}") from exc

        return str(result.get("id", ""))

    def download_payload(self, file_name: str = DEFAULT_FILE_NAME) -> Dict[str, Any]:
        existing = self.find_sync_file(file_name)
        if not existing:
            raise GoogleDriveSyncError("No encrypted backup found in Google Drive appDataFolder")

        request = self.service.files().get_media(fileId=existing["id"])
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)

        try:
            done = False
            while not done:
                _, done = downloader.next_chunk()
        except HttpError as exc:
            raise GoogleDriveSyncError(f"Failed to download encrypted payload: {exc}") from exc

        try:
            buffer.seek(0)
            return json.loads(buffer.read().decode("utf-8"))
        except Exception as exc:
            raise GoogleDriveSyncError(f"Downloaded payload is not valid JSON: {exc}") from exc

    def delete_payload(self, file_name: str = DEFAULT_FILE_NAME) -> bool:
        existing = self.find_sync_file(file_name)
        if not existing:
            return False
        try:
            self.service.files().delete(fileId=existing["id"]).execute()
            return True
        except HttpError as exc:
            raise GoogleDriveSyncError(f"Failed to delete encrypted payload: {exc}") from exc

    @staticmethod
    def _escape_query(value: str) -> str:
        return value.replace("'", "\\'")
