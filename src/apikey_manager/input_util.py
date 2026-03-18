"""Secure input utilities for collecting user data.

All prompts and validation messages are i18n-aware.
"""

from __future__ import annotations

import getpass
from typing import Optional

from .display import console, print_warning
from .i18n import _t


def prompt_password(message: str = "", confirm: bool = False) -> str:
    """Prompt for a password securely (hidden input). Optionally confirm.

    *message* should already be a translated string (e.g. _t("pw.master")).
    """
    if not message:
        message = _t("pw.master")
    while True:
        pw = getpass.getpass(f"  {message}")
        if not pw:
            print_warning(_t("prompt.pw_empty"))
            continue
        if confirm:
            pw2 = getpass.getpass(f"  {_t('prompt.confirm_pw')}")
            if pw != pw2:
                print_warning(_t("prompt.pw_mismatch"))
                continue
        return pw


def prompt_text(message: str, default: str = "", required: bool = False) -> str:
    """Prompt for text input with an optional default value.

    *message* should already be a translated string.
    """
    suffix = f" [{default}]" if default else ""
    while True:
        try:
            value = input(f"  {message}{suffix}: ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print()
            raise
        if not value and default:
            return default
        if not value and required:
            print_warning(_t("prompt.required"))
            continue
        return value


def prompt_choice(message: str, choices: list[str], default: Optional[str] = None) -> str:
    """Prompt user to pick from a list of choices."""
    display = ", ".join(f"[cyan]{c}[/cyan]" for c in choices)
    default_hint = f" [{default}]" if default else ""
    while True:
        value = input(f"  {message} ({display}){default_hint}: ").strip()
        if not value and default:
            return default
        if value in choices:
            return value
        print_warning(_t("prompt.choose_from", choices=", ".join(choices)))


def prompt_confirm(message: str, default: bool = False) -> bool:
    """Yes/No confirmation prompt."""
    hint = "Y/n" if default else "y/N"
    while True:
        value = input(f"  {message} ({hint}): ").strip().lower()
        if not value:
            return default
        if value in ("y", "yes"):
            return True
        if value in ("n", "no"):
            return False
        print_warning(_t("prompt.yes_no"))


def prompt_language() -> str:
    """Interactive language selection menu. Returns locale code."""
    from .i18n import lang

    console.print()
    console.print("  [bold cyan]%s[/bold cyan]" % _t("lang.select"))
    console.print()

    names = lang.lang_names
    codes = lang.available
    for i, code in enumerate(codes, 1):
        marker = ""
        if code == lang.locale:
            marker = " [dim]<-- current[/dim]"
        console.print(f"    [bold]{i}[/bold]  {code}  ({names[code]}){marker}")

    console.print()
    while True:
        try:
            raw = input("  > ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print()
            raise
        if not raw:
            return lang.locale
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(codes):
                return codes[idx]
        # Try direct locale code
        if raw in codes:
            return raw
        print_warning(_t("prompt.choose_from", choices=", ".join(str(i + 1) for i in range(len(codes)))))
