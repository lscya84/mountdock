from __future__ import annotations

import base64
import json
import secrets
from datetime import datetime, timezone
from typing import Any, Dict

from argon2.low_level import Type, hash_secret_raw
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

PAYLOAD_VERSION = 1
DEFAULT_TIME_COST = 3
DEFAULT_MEMORY_COST_KB = 65536
DEFAULT_PARALLELISM = 2
DEFAULT_KEY_LENGTH = 32
DEFAULT_NONCE_LENGTH = 12
DEFAULT_SALT_LENGTH = 16


class CryptoError(Exception):
    """Raised when encrypted rclone.conf payload processing fails."""


def _b64encode(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _b64decode(value: str, field_name: str) -> bytes:
    try:
        return base64.b64decode(value.encode("ascii"))
    except Exception as exc:
        raise CryptoError(f"Invalid base64 in field: {field_name}") from exc


def _derive_key(
    passphrase: str,
    salt: bytes,
    *,
    time_cost: int = DEFAULT_TIME_COST,
    memory_cost_kb: int = DEFAULT_MEMORY_COST_KB,
    parallelism: int = DEFAULT_PARALLELISM,
    length: int = DEFAULT_KEY_LENGTH,
) -> bytes:
    if not passphrase:
        raise CryptoError("Passphrase is required")
    if not salt:
        raise CryptoError("Salt is required")

    return hash_secret_raw(
        secret=passphrase.encode("utf-8"),
        salt=salt,
        time_cost=time_cost,
        memory_cost=memory_cost_kb,
        parallelism=parallelism,
        hash_len=length,
        type=Type.ID,
    )


def encrypt_rclone_conf(
    plaintext: bytes,
    passphrase: str,
    device_id: str,
    *,
    time_cost: int = DEFAULT_TIME_COST,
    memory_cost_kb: int = DEFAULT_MEMORY_COST_KB,
    parallelism: int = DEFAULT_PARALLELISM,
    length: int = DEFAULT_KEY_LENGTH,
) -> Dict[str, Any]:
    if not plaintext:
        raise CryptoError("Plaintext rclone.conf is empty")
    if not device_id:
        raise CryptoError("device_id is required")

    salt = secrets.token_bytes(DEFAULT_SALT_LENGTH)
    nonce = secrets.token_bytes(DEFAULT_NONCE_LENGTH)
    key = _derive_key(
        passphrase,
        salt,
        time_cost=time_cost,
        memory_cost_kb=memory_cost_kb,
        parallelism=parallelism,
        length=length,
    )

    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)

    return {
        "version": PAYLOAD_VERSION,
        "cipher": "AES-256-GCM",
        "kdf": {
            "name": "argon2id",
            "salt_b64": _b64encode(salt),
            "time_cost": time_cost,
            "memory_cost_kb": memory_cost_kb,
            "parallelism": parallelism,
            "length": length,
        },
        "nonce_b64": _b64encode(nonce),
        "ciphertext_b64": _b64encode(ciphertext),
        "meta": {
            "app": "MountDock",
            "format": "rclone.conf",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "device_id": device_id,
        },
    }


def decrypt_rclone_conf(payload: Dict[str, Any], passphrase: str) -> bytes:
    if not isinstance(payload, dict):
        raise CryptoError("Payload must be a dictionary")
    if payload.get("version") != PAYLOAD_VERSION:
        raise CryptoError(f"Unsupported payload version: {payload.get('version')}")
    if payload.get("cipher") != "AES-256-GCM":
        raise CryptoError("Unsupported cipher")

    kdf = payload.get("kdf") or {}
    if kdf.get("name") != "argon2id":
        raise CryptoError("Unsupported KDF")

    salt = _b64decode(kdf.get("salt_b64", ""), "kdf.salt_b64")
    nonce = _b64decode(payload.get("nonce_b64", ""), "nonce_b64")
    ciphertext = _b64decode(payload.get("ciphertext_b64", ""), "ciphertext_b64")

    key = _derive_key(
        passphrase,
        salt,
        time_cost=int(kdf.get("time_cost", DEFAULT_TIME_COST)),
        memory_cost_kb=int(kdf.get("memory_cost_kb", DEFAULT_MEMORY_COST_KB)),
        parallelism=int(kdf.get("parallelism", DEFAULT_PARALLELISM)),
        length=int(kdf.get("length", DEFAULT_KEY_LENGTH)),
    )

    try:
        return AESGCM(key).decrypt(nonce, ciphertext, None)
    except Exception as exc:
        raise CryptoError("Failed to decrypt payload. Passphrase may be wrong or payload is corrupted") from exc


def dumps_payload(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False)


def loads_payload(payload_text: str) -> Dict[str, Any]:
    try:
        loaded = json.loads(payload_text)
    except json.JSONDecodeError as exc:
        raise CryptoError("Payload is not valid JSON") from exc

    if not isinstance(loaded, dict):
        raise CryptoError("Payload JSON must be an object")
    return loaded
