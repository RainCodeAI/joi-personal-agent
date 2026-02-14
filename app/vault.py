import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from pathlib import Path
import json
from app.config import settings

VAULT_DIR = Path("./data/vault")
VAULT_FILE = VAULT_DIR / "secrets.json"

def _get_key() -> bytes:
    passphrase = settings.vault_passphrase
    if not passphrase:
        raise ValueError("VAULT_PASSPHRASE not set in .env")
    salt = b'static_salt_for_mvp'  # In production, use a random salt per user
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(passphrase.encode()))
    return key

def encrypt_data(data: str) -> str:
    f = Fernet(_get_key())
    return f.encrypt(data.encode()).decode()

def decrypt_data(encrypted: str) -> str:
    f = Fernet(_get_key())
    return f.decrypt(encrypted.encode()).decode()

def store_secret(key: str, value: str):
    VAULT_DIR.mkdir(parents=True, exist_ok=True)
    secrets = {}
    if VAULT_FILE.exists():
        with open(VAULT_FILE, 'r') as f:
            encrypted_secrets = json.load(f)
        for k, v in encrypted_secrets.items():
            secrets[k] = decrypt_data(v)
    secrets[key] = value
    encrypted_secrets = {k: encrypt_data(v) for k, v in secrets.items()}
    with open(VAULT_FILE, 'w') as f:
        json.dump(encrypted_secrets, f)

def get_secret(key: str) -> str:
    if not VAULT_FILE.exists():
        raise KeyError(f"Secret {key} not found")
    with open(VAULT_FILE, 'r') as f:
        encrypted_secrets = json.load(f)
    if key not in encrypted_secrets:
        raise KeyError(f"Secret {key} not found")
    return decrypt_data(encrypted_secrets[key])

def delete_secret(key: str):
    if not VAULT_FILE.exists():
        return
    with open(VAULT_FILE, 'r') as f:
        encrypted_secrets = json.load(f)
    if key in encrypted_secrets:
        del encrypted_secrets[key]
        with open(VAULT_FILE, 'w') as f:
            json.dump(encrypted_secrets, f)
