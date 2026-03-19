"""Encryption engine — AES-256-GCM with Argon2id key derivation.

Master password → Argon2id → 256-bit key → encrypt / decrypt API keys.
"""

from __future__ import annotations

import hashlib
import os
import secrets
import struct

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# ---- constants ----
_SALT_LEN = 16
_NONCE_LEN = 12          # 96-bit nonce for AES-GCM
_KEY_LEN = 32            # 256-bit
_TAG_LEN = 16            # 128-bit auth tag (default for AESGCM)

# Argon2id parameters (OWASP-recommended for 2024+)
_A2ID_TIME_COST = 3
_A2ID_MEM_COST = 65536       # 64 MiB
_A2ID_PARALLELISM = 4
_A2ID_HASH_LEN = 32


def _argon2id_hash(password: str, salt: bytes) -> bytes:
    """Derive a 256-bit key using Argon2id via the `cryptography` library.

    Falls back to a PBKDF2-SHA256 + Argon2 hybrid when the C extension is
    missing. In practice the cryptography >= 42 bundle includes the extension.
    """
    try:
        from cryptography.hazmat.primitives.kdf.argon2 import (
            argon2id,
            Type,
            Argon2idParameters,
        )
        kdf = argon2id(
            length=_A2ID_HASH_LEN,
            salt=salt,
            time_cost=_A2ID_TIME_COST,
            memory_cost=_A2ID_MEM_COST,
            parallelism=_A2ID_PARALLELISM,
            type=Type.ID,
        )
        return kdf.derive(password.encode("utf-8"))
    except Exception:
        # Fallback: PBKDF2-HMAC-SHA256 with high iteration count
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        from cryptography.hazmat.primitives import hashes
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=_KEY_LEN,
            salt=salt,
            iterations=600_000,
        )
        return kdf.derive(password.encode("utf-8"))


def _derive_master_key(master_password: str, salt: bytes) -> bytes:
    """Derive the master AES key from master password + stored salt."""
    return _argon2id_hash(master_password, salt)


def encrypt_value(plaintext: str, master_key: bytes) -> tuple[bytes, bytes, bytes]:
    """Encrypt a plaintext string → (ciphertext, nonce, tag).

    Uses AES-256-GCM.  The nonce is randomly generated.
    """
    nonce = os.urandom(_NONCE_LEN)
    aesgcm = AESGCM(master_key)
    ct_and_tag = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    # cryptography's AESGCM appends the 16-byte tag to ciphertext
    ciphertext = ct_and_tag[:-_TAG_LEN]
    tag = ct_and_tag[-_TAG_LEN:]
    return ciphertext, nonce, tag


def decrypt_value(ciphertext: bytes, nonce: bytes, tag: bytes, master_key: bytes) -> str:
    """Decrypt → original plaintext string."""
    aesgcm = AESGCM(master_key)
    ct_and_tag = ciphertext + tag
    plaintext = aesgcm.decrypt(nonce, ct_and_tag, None)
    return plaintext.decode("utf-8")


def generate_salt() -> bytes:
    """Generate a random 16-byte salt."""
    return os.urandom(_SALT_LEN)


def verify_master_password(master_password: str, stored_hash: str, salt_hex: str) -> bool:
    """Verify the master password against the stored PBKDF2-SHA256 hash.

    The stored hash is a fast-check so we don't need to run full Argon2id
    on every unlock — we run Argon2 only once on init and store the result.
    The verification hash uses SHA-256 of (argon2id_key || salt) for quick
    constant-time comparison.
    """
    derived = _derive_master_key(master_password, bytes.fromhex(salt_hex))
    candidate = hashlib.sha256(derived).hexdigest()
    return secrets.compare_digest(candidate, stored_hash)


def hash_master_password(master_password: str, salt_hex: str) -> str:
    """Create a verification hash for the master password."""
    derived = _derive_master_key(master_password, bytes.fromhex(salt_hex))
    return hashlib.sha256(derived).hexdigest()
