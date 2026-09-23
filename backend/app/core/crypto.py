import base64
import hashlib
import hmac
import os
from cryptography.fernet import Fernet
from app.core.config import settings

_fernet_instance = None

def get_fernet() -> Fernet:
    global _fernet_instance
    if _fernet_instance is None:
        key = settings.ROUTER_MASTER_KEY
        if not key:
            raise RuntimeError("ROUTER_MASTER_KEY must be configured before encrypting secrets")
        elif isinstance(key, str):
            # Ensure key is valid 32-byte urlsafe base64
            key_bytes = key.strip().encode()
            try:
                # Test validity
                Fernet(key_bytes)
                key = key_bytes.decode()
            except Exception:
                # If a plain passphrase was passed, derive 32-byte urlsafe base64 key
                derived = hashlib.sha256(key_bytes).digest()
                key = base64.urlsafe_b64encode(derived).decode()
        _fernet_instance = Fernet(key.encode() if isinstance(key, str) else key)
    return _fernet_instance

def encrypt_secret(secret: str) -> str:
    """Encrypt a plaintext secret using authenticated Fernet (AES-128-CBC + HMAC-SHA256)."""
    if not secret:
        return ""
    f = get_fernet()
    return f.encrypt(secret.encode("utf-8")).decode("utf-8")

def decrypt_secret(encrypted: str) -> str:
    """Decrypt an encrypted secret."""
    if not encrypted:
        return ""
    f = get_fernet()
    return f.decrypt(encrypted.encode("utf-8")).decode("utf-8")

def compute_fingerprint(secret: str) -> str:
    """Compute HMAC-SHA256 fingerprint of secret for duplicate detection without storing plaintext."""
    if not secret:
        return ""
    salt = settings.FINGERPRINT_SALT.encode("utf-8")
    return hmac.new(salt, secret.strip().encode("utf-8"), hashlib.sha256).hexdigest()

def mask_secret(secret: str) -> str:
    """Mask secret safely for UI display. Never expose full upstream credentials."""
    if not secret:
        return ""
    secret = secret.strip()
    if len(secret) <= 8:
        return "••••••••"
    if secret.startswith("sk-router-"):
        return f"sk-router-••••{secret[-4:]}"
    if secret.startswith("AIzaSy"):
        return f"AIzaSy••••••••••{secret[-4:]}"
    if secret.startswith("sk-ant-"):
        return f"sk-ant-••••{secret[-4:]}"
    if secret.startswith("sk-"):
        return f"sk-••••{secret[-4:]}"
    # Generic format: first 4 and last 4 characters visible, middle masked
    return f"{secret[:4]}••••••••{secret[-4:]}"
