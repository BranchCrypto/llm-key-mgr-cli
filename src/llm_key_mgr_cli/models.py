"""Data models for API key entries."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from enum import Enum
from typing import Optional


class Protocol(str, Enum):
    """Supported API protocols."""
    OPENAI = "OpenAI"
    ANTHROPIC = "Anthropic"


@dataclass
class KeyEntry:
    """Represents a single stored API key with metadata."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    protocol: Protocol = Protocol.OPENAI
    base_url: str = ""
    model: str = ""
    api_key_encrypted: bytes = b""      # stored encrypted
    api_key_iv: bytes = b""             # AES IV
    api_key_tag: bytes = b""            # AES-GCM auth tag
    expires_at: Optional[str] = None    # YYYY-MM-DD or None (never expires)
    notes: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    # ---- convenience helpers ----

    class ProtocolError(ValueError):
        """Raised when an invalid protocol is provided."""
        def __init__(self, value: str):
            self.value = value

    class DateError(ValueError):
        """Raised when an invalid date string is provided."""
        def __init__(self, value: str):
            self.value = value

    @staticmethod
    def parse_protocol(value: str) -> Protocol:
        """Case-insensitive protocol parsing."""
        v = value.strip().lower()
        if v in ("openai", "o", "1"):
            return Protocol.OPENAI
        if v in ("anthropic", "a", "2"):
            return Protocol.ANTHROPIC
        raise KeyEntry.ProtocolError(value)

    @staticmethod
    def parse_date(value: str) -> Optional[str]:
        """Parse a date string into YYYY-MM-DD format. Returns None for empty / 'never'."""
        v = value.strip().lower()
        if v in ("", "never", "none", "none", "-"):
            return None
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m-%d-%Y", "%m/%d/%Y", "%d-%m-%Y", "%d/%m/%Y"):
            try:
                return datetime.strptime(v, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        raise KeyEntry.DateError(value)

    @staticmethod
    def is_expired(expires_at: Optional[str]) -> Optional[bool]:
        """Return True/False/None (None = no expiry set)."""
        if expires_at is None:
            return None
        try:
            exp = datetime.strptime(expires_at, "%Y-%m-%d").date()
            return date.today() > exp
        except ValueError:
            return None

    @staticmethod
    def days_until_expiry(expires_at: Optional[str]) -> Optional[int]:
        """Days remaining. None if never expires."""
        if expires_at is None:
            return None
        try:
            exp = datetime.strptime(expires_at, "%Y-%m-%d").date()
            return (exp - date.today()).days
        except ValueError:
            return None

    def touch(self):
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now().isoformat()
