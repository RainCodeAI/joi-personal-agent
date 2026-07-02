import base64
import os
import threading
from cryptography.fernet import Fernet
from cryptography.fernet import InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from pathlib import Path
import json
from app.config import settings

VAULT_DIR = Path("./data/vault")
VAULT_FILE = VAULT_DIR / "secrets.json"
SALT_FILE = VAULT_DIR / "salt.bin"
LEGACY_STATIC_SALT = b'static_salt_for_mvp'

# Serializes the read-modify-write cycle in store/delete so concurrent writers
# (e.g. an OAuth callback and a settings save) can't corrupt secrets.json.
_VAULT_LOCK = threading.RLock()

def _get_salt() -> bytes:
    VAULT_DIR.mkdir(parents=True, exist_ok=True)
    if SALT_FILE.exists():
        return SALT_FILE.read_bytes()
    salt = os.urandom(16)
    SALT_FILE.write_bytes(salt)
    return salt


def _derive_key(salt: bytes) -> bytes:
    passphrase = settings.vault_passphrase
    if not passphrase:
        raise ValueError("VAULT_PASSPHRASE not set in .env")
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(passphrase.encode()))
    return key


def _get_key() -> bytes:
    return _derive_key(_get_salt())

def encrypt_data(data: str) -> str:
    f = Fernet(_get_key())
    return f.encrypt(data.encode()).decode()

def decrypt_data(encrypted: str) -> str:
    current = Fernet(_get_key())
    try:
        return current.decrypt(encrypted.encode()).decode()
    except InvalidToken:
        # Fall back to the legacy static salt for secrets written before the
        # per-install random salt existed.
        try:
            legacy = Fernet(_derive_key(LEGACY_STATIC_SALT))
            return legacy.decrypt(encrypted.encode()).decode()
        except InvalidToken as exc:
            raise ValueError(
                "Could not decrypt secret — VAULT_PASSPHRASE is likely wrong or the "
                "vault salt changed. Fix the passphrase or re-create the vault."
            ) from exc


def _write_secrets(encrypted_secrets: dict) -> None:
    VAULT_DIR.mkdir(parents=True, exist_ok=True)
    temporary = VAULT_FILE.with_suffix(VAULT_FILE.suffix + ".tmp")
    with open(temporary, 'w') as f:
        json.dump(encrypted_secrets, f)
    os.replace(temporary, VAULT_FILE)


def store_secret(key: str, value: str):
    with _VAULT_LOCK:
        secrets = {}
        if VAULT_FILE.exists():
            with open(VAULT_FILE, 'r') as f:
                encrypted_secrets = json.load(f)
            for k, v in encrypted_secrets.items():
                secrets[k] = decrypt_data(v)
        secrets[key] = value
        encrypted_secrets = {k: encrypt_data(v) for k, v in secrets.items()}
        _write_secrets(encrypted_secrets)

def get_secret(key: str) -> str:
    if not VAULT_FILE.exists():
        raise KeyError(f"Secret {key} not found")
    with open(VAULT_FILE, 'r') as f:
        encrypted_secrets = json.load(f)
    if key not in encrypted_secrets:
        raise KeyError(f"Secret {key} not found")
    return decrypt_data(encrypted_secrets[key])

def delete_secret(key: str):
    with _VAULT_LOCK:
        if not VAULT_FILE.exists():
            return
        with open(VAULT_FILE, 'r') as f:
            encrypted_secrets = json.load(f)
        if key in encrypted_secrets:
            del encrypted_secrets[key]
            _write_secrets(encrypted_secrets)
