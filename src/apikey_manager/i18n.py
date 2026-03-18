"""Lightweight i18n engine.

No gettext, no .po files.  Locale data lives in JSON alongside the source.
The user's language choice is persisted in ~/.apikey_config.json.

Usage
-----
    from .i18n import lang

    lang.set_locale("zh_CN")
    lang.set_locale("en_US")

    lang.t("key")                         # simple lookup
    lang.t("welcome.title")                # dotted path
    lang.t("keys.count", n=42)             # formatted
    lang.t("confirm.delete", name="foo")   # keyword formatted
"""

from __future__ import annotations

import json
import locale as _stdlib_locale
import os
import sys
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Locale directory — alongside this file
# ---------------------------------------------------------------------------
_LOCALE_DIR = Path(__file__).parent / "locales"

# ---------------------------------------------------------------------------
# Fallback strings (en_US) baked in so the tool never crashes even if the
# locale file is missing.
# ---------------------------------------------------------------------------
_FALLBACK: dict[str, Any] = {
    # ---- general ----
    "version": "v{version}",
    "banner.title": "API Key Manager",
    # ---- prompts ----
    "prompt.required": "This field is required.",
    "prompt.yes_no": "Please enter 'y' or 'n'.",
    "prompt.choose_from": "Please choose from: {choices}",
    "prompt.pw_empty": "Password cannot be empty.",
    "prompt.pw_mismatch": "Passwords do not match. Please try again.",
    "prompt.confirm_pw": "Confirm password: ",
    # ---- init ----
    "init.title": "Create your master password",
    "init.hint": "This password protects all your API keys. Do NOT forget it!",
    "init.pw_too_short": "Password must be at least {min_len} characters.",
    "init.created": "Vault created at {path}",
    "init.next_step": "Run {cmd} to store your first API key.",
    # ---- language ----
    "lang.select": "Select language / 选择语言",
    "lang.detected": "Detected system locale: {locale}",
    "lang.saved": "Language set to {lang}.",
    "lang.config_path": "Config saved to {path}",
    # ---- vault ----
    "vault.not_found": "Vault not found. Run {cmd} first.",
    "vault.already_exists": "Vault already exists at {path}",
    "vault.overwrite": "Overwrite existing vault? This will delete all stored keys.",
    "vault.unlocked": "Vault unlocked.",
    # ---- password ----
    "pw.master": "Master password: ",
    "pw.master_new": "New master password: ",
    "pw.master_current": "Current master password: ",
    "pw.incorrect": "Incorrect master password.",
    "pw.change_title": "Change master password",
    "pw.changed": "Master password changed. All keys re-encrypted with new password.",
    "pw.change_failed": "Failed to change password.",
    # ---- add ----
    "add.title": "Add new API key",
    "add.name": "Name",
    "add.protocol": "Protocol",
    "add.base_url": "Base URL",
    "add.model": "Model",
    "add.api_key": "API Key: ",
    "add.api_key_required": "API key is required.",
    "add.expiry": "Expiry date (YYYY-MM-DD, or blank for never)",
    "add.notes": "Notes",
    "add.success": "API key '{name}' added successfully.",
    "add.duplicate": "An entry named '{name}' already exists.",
    # ---- list ----
    "list.title": "Stored API Keys",
    "list.empty": "No API keys stored yet.",
    "list.empty_hint": "Run {cmd} to add your first key.",
    "list.total": "Total: {n} key(s)",
    # ---- table headers ----
    "col.id": "#",
    "col.name": "Name",
    "col.protocol": "Protocol",
    "col.base_url": "Base URL",
    "col.model": "Model",
    "col.api_key": "API Key",
    "col.expires": "Expires",
    "col.notes": "Notes",
    # ---- show / detail ----
    "detail.name": "Name",
    "detail.id": "ID",
    "detail.protocol": "Protocol",
    "detail.base_url": "Base URL",
    "detail.model": "Model",
    "detail.api_key": "API Key",
    "detail.expires": "Expires",
    "detail.status": "Status",
    "detail.notes": "Notes",
    "detail.created": "Created",
    "detail.updated": "Updated",
    "detail.never": "Never",
    "detail.expired": "EXPIRED ({date})",
    "detail.days_left": "{days}d left ({date})",
    "detail.valid": "Valid",
    "detail.status_expired": "!! EXPIRED",
    "detail.status_days": "{days} day(s) remaining",
    # ---- update ----
    "update.title": "Update '{name}'",
    "update.hint": "Press Enter to keep current value.",
    "update.change_key": "Change API key?",
    "update.new_api_key": "New API Key: ",
    "update.expiry_date": "Expiry date",
    "update.no_changes": "No changes made.",
    "update.success": "Entry '{name}' updated successfully.",
    # ---- delete ----
    "delete.confirm": "Delete '{name}' permanently?",
    "delete.sure": "Are you really sure? This cannot be undone.",
    "delete.success": "Entry '{name}' deleted.",
    "delete.not_found": "Entry '{name}' not found.",
    # ---- show command ----
    "show.reveal_confirm": "Reveal the full API key for '{name}'?",
    "show.masked": "Showing masked key.",
    "show.visible_warning": "API key is visible above. Clear your terminal after use.",
    # ---- export ----
    "export.pw": "Backup encryption password: ",
    "export.pw_too_short": "Backup password must be at least 4 characters.",
    "export.empty": "No keys to export.",
    "export.success": "Exported {n} key(s) to {path}",
    "export.keep_safe": "Keep this file and the backup password safe!",
    # ---- import ----
    "import.not_found": "File not found: {path}",
    "import.invalid_file": "Invalid backup file (too small).",
    "import.pw": "Backup decryption password: ",
    "import.decrypt_failed": "Decryption failed. Wrong password or corrupted file.",
    "import.skipping": "Skipping '{name}' (already exists)",
    "import.skipping_no_key": "Skipping '{name}' (no API key in backup)",
    "import.imported": "Imported '{name}'",
    "import.success": "Imported {n} key(s), skipped {m}.",
    # ---- generic ----
    "aborted": "Aborted.",
    "interrupted": "Interrupted.",
    "never": "never",
    # ---- models ----
    "model.invalid_protocol": "Invalid protocol '{value}'. Choose: OpenAI, Anthropic",
    "model.invalid_date": "Cannot parse date '{value}'. Expected format: YYYY-MM-DD",
}

# Language display names (keyed by locale code)
_LANG_NAMES: dict[str, str] = {
    "zh_CN": "中文",
    "en_US": "English",
}

# Available locales (order matters — shown in this order to user)
_AVAILABLE = list(_LANG_NAMES.keys())


# ===========================================================================
# Lang class
# ===========================================================================

class Lang:
    """Singleton i18n manager."""

    def __init__(self) -> None:
        self._locale: str = "en_US"
        self._strings: dict[str, Any] = {}
        self._config_path = Path.home() / ".apikey_config.json"

    # ---- properties ----

    @property
    def locale(self) -> str:
        return self._locale

    @property
    def available(self) -> list[str]:
        return list(_AVAILABLE)

    @property
    def lang_names(self) -> dict[str, str]:
        return dict(_LANG_NAMES)

    # ---- public API ----

    def detect_system_locale(self) -> str:
        """Best-effort detection of the system locale."""
        try:
            loc, _ = _stdlib_locale.getdefaultlocale()
        except Exception:
            loc = None

        if loc:
            # Normalise: zh_CN.UTF-8 -> zh_CN, en_US.ISO8859-1 -> en_US
            code = loc.split(".")[0]
            if code in _AVAILABLE:
                return code
            # Try just the language part: zh -> zh_CN
            lang_part = code.split("_")[0]
            for a in _AVAILABLE:
                if a.startswith(lang_part):
                    return a

        # Check env vars
        for env_key in ("LANG", "LANGUAGE", "LC_ALL", "LC_MESSAGES"):
            val = os.environ.get(env_key, "")
            if val:
                code = val.split(".")[0].split("_")[0]
                for a in _AVAILABLE:
                    if a.startswith(code):
                        return a

        return "en_US"

    def set_locale(self, locale_code: str) -> None:
        """Switch to a locale.  Falls back to en_US if not available."""
        if locale_code not in _AVAILABLE:
            locale_code = "en_US"
        self._locale = locale_code

        # Load from JSON if possible, otherwise use fallback
        json_path = _LOCALE_DIR / f"{locale_code}.json"
        if json_path.exists():
            try:
                self._strings = json.loads(json_path.read_text(encoding="utf-8"))
            except Exception:
                self._strings = {}
        else:
            self._strings = {}

    def save_config(self) -> None:
        """Persist locale choice to disk."""
        self._config_path.write_text(
            json.dumps({"locale": self._locale}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def load_config(self) -> Optional[str]:
        """Read persisted locale, or None."""
        try:
            if self._config_path.exists():
                data = json.loads(self._config_path.read_text(encoding="utf-8"))
                loc = data.get("locale", "")
                if loc in _AVAILABLE:
                    return loc
        except Exception:
            pass
        return None

    def t(self, key: str, **kwargs: Any) -> str:
        """Translate *key*, optionally formatting with *kwargs*.

        Templates use {key} style formatting (Python str.format).
        Falls back to raw key if nothing matches.
        """
        text = self._lookup(key)
        if kwargs:
            try:
                return text.format(**kwargs)
            except (KeyError, IndexError, ValueError):
                pass
        return text

    # ---- internals ----

    def _lookup(self, key: str) -> str:
        # 1) Try flat lookup (JSON uses dotted keys like "add.title")
        if key in self._strings and isinstance(self._strings[key], str):
            return self._strings[key]

        # 2) Try nested lookup (supports dotted path navigation)
        parts = key.split(".")
        obj: Any = self._strings
        try:
            for p in parts:
                obj = obj[p]
            if isinstance(obj, str):
                return obj
        except (KeyError, TypeError):
            pass

        # 3) Fallback dict (flat first)
        if key in _FALLBACK and isinstance(_FALLBACK[key], str):
            return _FALLBACK[key]

        # 4) Fallback nested
        obj = _FALLBACK
        try:
            for p in parts:
                obj = obj[p]
            if isinstance(obj, str):
                return obj
        except (KeyError, TypeError):
            pass

        return key  # last resort


# ===========================================================================
# Module-level singleton
# ===========================================================================
lang = Lang()

# Convenience alias used everywhere
_t = lang.t
