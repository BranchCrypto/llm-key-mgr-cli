"""Secure storage layer — SQLite database with encrypted API keys.

Schema:
    _meta          — single row: version, salt_hex, master_hash, created_at
    api_keys       — all key entries (API key value is encrypted)
"""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .models import KeyEntry, Protocol
from .crypto import (
    encrypt_value,
    decrypt_value,
    generate_salt,
    hash_master_password,
    verify_master_password,
    _derive_master_key,
)


# ---- default paths ----

_DEFAULT_DB_NAME = ".apikey_vault.db"

def default_db_path() -> Path:
    """Vault DB stored in user home directory (not in repo / cwd)."""
    return Path.home() / _DEFAULT_DB_NAME


class Vault:
    """Encrypted API key vault backed by SQLite."""

    def __init__(self, db_path: Optional[str | Path] = None):
        self.db_path = Path(db_path) if db_path else default_db_path()
        self._conn: Optional[sqlite3.Connection] = None
        self._master_key: Optional[bytes] = None

    # ---- connection management ----

    def _connect(self) -> sqlite3.Connection:
        if self._conn is not None:
            return self._conn
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute("PRAGMA locking_mode=NORMAL")
        return self._conn

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None
        self._master_key = None  # wipe from memory

    @property
    def exists(self) -> bool:
        return self.db_path.exists()

    # ---- init vault (first time) ----

    def init_vault(self, master_password: str) -> bool:
        """Create a new vault with the given master password. Returns True on success."""
        if self.exists:
            return False

        salt = generate_salt()
        salt_hex = salt.hex()
        master_hash = hash_master_password(master_password, salt_hex)

        conn = self._connect()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS _meta (
                    key   TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS api_keys (
                    id              TEXT PRIMARY KEY,
                    name            TEXT NOT NULL,
                    protocol        TEXT NOT NULL,
                    base_url        TEXT NOT NULL DEFAULT '',
                    model           TEXT NOT NULL DEFAULT '',
                    api_key_enc     BLOB NOT NULL,
                    api_key_iv      BLOB NOT NULL,
                    api_key_tag     BLOB NOT NULL,
                    expires_at      TEXT,
                    notes           TEXT NOT NULL DEFAULT '',
                    created_at      TEXT NOT NULL,
                    updated_at      TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_api_keys_name
                ON api_keys (name)
            """)

            now = datetime.now().isoformat()
            conn.executemany(
                "INSERT INTO _meta (key, value) VALUES (?, ?)",
                [
                    ("version", "1"),
                    ("salt_hex", salt_hex),
                    ("master_hash", master_hash),
                    ("created_at", now),
                ],
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        return True

    # ---- unlock ----

    def unlock(self, master_password: str) -> bool:
        """Unlock the vault. Returns True if password is correct."""
        conn = self._connect()
        row = conn.execute("SELECT value FROM _meta WHERE key = 'salt_hex'").fetchone()
        if not row:
            return False
        salt_hex = row["value"]

        row = conn.execute("SELECT value FROM _meta WHERE key = 'master_hash'").fetchone()
        if not row:
            return False
        master_hash = row["value"]

        if not verify_master_password(master_password, master_hash, salt_hex):
            return False

        # Derive actual encryption key
        self._master_key = _derive_master_key(master_password, bytes.fromhex(salt_hex))
        return True

    # ---- CRUD ----

    def require_unlock(self):
        if self._master_key is None:
            raise PermissionError("Vault is locked. Run 'apikey-mgr init' or unlock first.")

    def add_entry(self, entry: KeyEntry, api_key_plaintext: str) -> KeyEntry:
        """Insert a new key entry (API key is encrypted before storage)."""
        self.require_unlock()
        ct, iv, tag = encrypt_value(api_key_plaintext, self._master_key)
        entry.api_key_encrypted = ct
        entry.api_key_iv = iv
        entry.api_key_tag = tag

        conn = self._connect()
        try:
            conn.execute(
                """INSERT INTO api_keys
                   (id, name, protocol, base_url, model,
                    api_key_enc, api_key_iv, api_key_tag,
                    expires_at, notes, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    entry.id, entry.name, entry.protocol.value,
                    entry.base_url, entry.model,
                    ct, iv, tag,
                    entry.expires_at, entry.notes,
                    entry.created_at, entry.updated_at,
                ),
            )
            conn.commit()
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"Entry with name '{entry.name}' already exists.") from exc
        return entry

    def list_entries(self) -> List[KeyEntry]:
        """List all entries (API keys remain encrypted — only metadata)."""
        self.require_unlock()
        conn = self._connect()
        rows = conn.execute(
            "SELECT * FROM api_keys ORDER BY created_at DESC"
        ).fetchall()
        entries = []
        for r in rows:
            e = KeyEntry(
                id=r["id"],
                name=r["name"],
                protocol=Protocol(r["protocol"]),
                base_url=r["base_url"],
                model=r["model"],
                api_key_encrypted=r["api_key_enc"],
                api_key_iv=r["api_key_iv"],
                api_key_tag=r["api_key_tag"],
                expires_at=r["expires_at"],
                notes=r["notes"],
                created_at=r["created_at"],
                updated_at=r["updated_at"],
            )
            entries.append(e)
        return entries

    def get_entry(self, name: str) -> Optional[KeyEntry]:
        """Get entry by name (API key stays encrypted)."""
        self.require_unlock()
        conn = self._connect()
        r = conn.execute(
            "SELECT * FROM api_keys WHERE name = ?", (name,)
        ).fetchone()
        if not r:
            return None
        return KeyEntry(
            id=r["id"],
            name=r["name"],
            protocol=Protocol(r["protocol"]),
            base_url=r["base_url"],
            model=r["model"],
            api_key_encrypted=r["api_key_enc"],
            api_key_iv=r["api_key_iv"],
            api_key_tag=r["api_key_tag"],
            expires_at=r["expires_at"],
            notes=r["notes"],
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        )

    def decrypt_api_key(self, entry: KeyEntry) -> str:
        """Decrypt the API key for a given entry."""
        self.require_unlock()
        return decrypt_value(
            entry.api_key_encrypted,
            entry.api_key_iv,
            entry.api_key_tag,
            self._master_key,
        )

    def update_entry(self, name: str, **kwargs) -> Optional[KeyEntry]:
        """Update fields of an existing entry.

        Accepted kwargs: protocol, base_url, model, api_key_plaintext,
                         expires_at, notes, new_name.
        """
        self.require_unlock()
        entry = self.get_entry(name)
        if entry is None:
            return None

        if "api_key_plaintext" in kwargs:
            ct, iv, tag = encrypt_value(
                kwargs.pop("api_key_plaintext"), self._master_key
            )
            kwargs["api_key_enc"] = ct
            kwargs["api_key_iv"] = iv
            kwargs["api_key_tag"] = tag

        if "new_name" in kwargs:
            kwargs["name"] = kwargs.pop("new_name")

        if "protocol" in kwargs:
            p = kwargs["protocol"]
            kwargs["protocol"] = p.value if isinstance(p, Protocol) else str(p)

        if not kwargs:
            return entry

        kwargs["updated_at"] = datetime.now().isoformat()

        set_clause = ", ".join(f"{k} = ?" for k in kwargs)
        values = list(kwargs.values()) + [name]

        conn = self._connect()
        try:
            conn.execute(
                f"UPDATE api_keys SET {set_clause} WHERE name = ?",
                values,
            )
            conn.commit()
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"Entry with name '{kwargs.get('name')}' already exists.") from exc

        return self.get_entry(kwargs.get("name", name))

    def delete_entry(self, name: str) -> bool:
        """Delete entry by name. Returns True if deleted."""
        self.require_unlock()
        conn = self._connect()
        cursor = conn.execute(
            "DELETE FROM api_keys WHERE name = ?", (name,)
        )
        conn.commit()
        return cursor.rowcount > 0

    def change_master_password(self, old_password: str, new_password: str) -> bool:
        """Re-encrypt all keys with a new master password."""
        # Verify old password
        conn = self._connect()
        row = conn.execute("SELECT value FROM _meta WHERE key = 'salt_hex'").fetchone()
        if not row:
            return False
        salt_hex = row["value"]
        row = conn.execute("SELECT value FROM _meta WHERE key = 'master_hash'").fetchone()
        if not row:
            return False

        if not verify_master_password(old_password, row["value"], salt_hex):
            return False

        old_key = _derive_master_key(
            old_password, bytes.fromhex(salt_hex)
        )

        # Generate new salt & hash
        new_salt = generate_salt()
        new_salt_hex = new_salt.hex()
        new_hash = hash_master_password(new_password, new_salt_hex)
        new_key = _derive_master_key(
            new_password, new_salt
        )

        # Re-encrypt all API keys
        rows = conn.execute("SELECT name, api_key_enc, api_key_iv, api_key_tag FROM api_keys").fetchall()
        for r in rows:
            plaintext = decrypt_value(r["api_key_enc"], r["api_key_iv"], r["api_key_tag"], old_key)
            ct, iv, tag = encrypt_value(plaintext, new_key)
            conn.execute(
                "UPDATE api_keys SET api_key_enc=?, api_key_iv=?, api_key_tag=? WHERE name=?",
                (ct, iv, tag, r["name"]),
            )

        conn.execute("UPDATE _meta SET value=? WHERE key='salt_hex'", (new_salt_hex,))
        conn.execute("UPDATE _meta SET value=? WHERE key='master_hash'", (new_hash,))
        conn.commit()

        self._master_key = new_key
        return True
