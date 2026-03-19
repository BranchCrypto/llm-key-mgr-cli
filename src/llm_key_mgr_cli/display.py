"""Rich display utilities for API key management.

All user-visible strings go through i18n.t() for translation.
No emoji characters to ensure compatibility with all terminal encodings.
"""

from __future__ import annotations

from typing import List, Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

from .models import KeyEntry, Protocol
from .i18n import _t

console = Console()

# ---- color palette ----
_CLR_OK = "green"
_CLR_WARN = "yellow"
_CLR_ERR = "red"
_CLR_DIM = "dim"
_CLR_PROTOCOL_OPENAI = "cyan"
_CLR_PROTOCOL_ANTHROPIC = "magenta"


def _mask_key(entry: KeyEntry) -> str:
    return "****...%s" % entry.id[-4:]


def _expiry_text(expires_at: Optional[str]) -> Text:
    expired = KeyEntry.is_expired(expires_at)
    days = KeyEntry.days_until_expiry(expires_at)

    if expires_at is None:
        return Text(_t("detail.never"), style=_CLR_DIM)
    if expired:
        return Text(_t("detail.expired", date=expires_at), style=_CLR_ERR)
    if days is not None and days <= 7:
        return Text(_t("detail.days_left", days=days, date=expires_at), style=_CLR_WARN)
    return Text(expires_at, style=_CLR_OK)


def _protocol_colored(protocol: Protocol) -> str:
    color = _CLR_PROTOCOL_OPENAI if protocol == Protocol.OPENAI else _CLR_PROTOCOL_ANTHROPIC
    return "[%s]%s[/%s]" % (color, protocol.value, color)


def print_banner():
    banner = Text()
    banner.append("  [*] ", style="bold")
    banner.append(_t("banner.title"), style="bold cyan")
    from . import __version__
    banner.append("  " + __version__, style="dim")
    console.print(Panel(banner, box=box.DOUBLE, border_style="cyan", padding=(0, 2)))


def print_entries_table(entries: List[KeyEntry]):
    if not entries:
        console.print()
        console.print("[bold yellow]  %s[/bold yellow]" % _t("list.empty"))
        console.print("  %s" % _t("list.empty_hint", cmd="[cyan]apikey-mgr add[/cyan]"))
        console.print()
        return

    table = Table(
        title="\n  " + _t("list.title"),
        box=box.ROUNDED,
        show_lines=True,
        title_style="bold cyan",
        header_style="bold white",
        border_style="dim",
        pad_edge=False,
        expand=True,
    )

    table.add_column(_t("col.id"), style="dim", justify="center", width=3)
    table.add_column(_t("col.name"), style="bold", min_width=10)
    table.add_column(_t("col.protocol"), justify="center", min_width=10)
    table.add_column(_t("col.base_url"), style="dim", min_width=20, max_width=45, no_wrap=True)
    table.add_column(_t("col.model"), min_width=8, max_width=30)
    table.add_column(_t("col.api_key"), min_width=24, max_width=30)
    table.add_column(_t("col.expires"), min_width=12, max_width=28)
    table.add_column(_t("col.notes"), style="dim", min_width=8, max_width=40)

    for i, entry in enumerate(entries, 1):
        notes = entry.notes if entry.notes else "[dim]-[/dim]"
        expired = KeyEntry.is_expired(entry.expires_at)
        row_style = "on red15" if expired else None

        table.add_row(
            str(i),
            entry.name,
            _protocol_colored(entry.protocol),
            entry.base_url,
            entry.model,
            _mask_key(entry),
            _expiry_text(entry.expires_at),
            notes,
            style=row_style,
        )

    console.print(table)
    console.print()
    console.print("  [dim]%s[/dim]" % _t("list.total", n=len(entries)))
    console.print()


def print_entry_detail(entry: KeyEntry, api_key_plaintext: Optional[str] = None):
    expired = KeyEntry.is_expired(entry.expires_at)
    days = KeyEntry.days_until_expiry(entry.expires_at)

    info_table = Table.grid(padding=(0, 2))
    info_table.add_column(style="bold cyan", min_width=14)
    info_table.add_column()

    info_table.add_row(_t("detail.name"), entry.name)
    info_table.add_row(_t("detail.id"), "[dim]%s[/dim]" % entry.id)
    info_table.add_row(_t("detail.protocol"), _protocol_colored(entry.protocol))
    info_table.add_row(_t("detail.base_url"), entry.base_url)
    info_table.add_row(_t("detail.model"), entry.model)

    if api_key_plaintext is not None:
        info_table.add_row(_t("detail.api_key"), "[bold green]%s[/bold green]" % api_key_plaintext)
    else:
        info_table.add_row(_t("detail.api_key"), _mask_key(entry))

    if entry.expires_at:
        info_table.add_row(_t("detail.expires"), str(_expiry_text(entry.expires_at)))
        if expired:
            info_table.add_row(_t("detail.status"), "[bold red]%s[/bold red]" % _t("detail.status_expired"))
        elif days is not None and days <= 30:
            info_table.add_row(_t("detail.status"), "[yellow]%s[/yellow]" % _t("detail.status_days", days=days))
        else:
            info_table.add_row(_t("detail.status"), "[green]%s[/green]" % _t("detail.valid"))
    else:
        info_table.add_row(_t("detail.expires"), "[dim]%s[/dim]" % _t("detail.never"))
        info_table.add_row(_t("detail.status"), "[green]%s[/green]" % _t("detail.valid"))

    info_table.add_row(_t("detail.notes"), entry.notes if entry.notes else "[dim]-[/dim]")
    info_table.add_row(_t("detail.created"), entry.created_at)
    info_table.add_row(_t("detail.updated"), entry.updated_at)

    console.print(Panel(info_table, title="  [*] %s" % entry.name, border_style="cyan", box=box.ROUNDED))


def print_success(msg: str):
    console.print()
    console.print("  [bold green]+[/bold green]  %s" % msg)
    console.print()


def print_error(msg: str):
    console.print()
    console.print("  [bold red]![/bold red]  %s" % msg)
    console.print()


def print_warning(msg: str):
    console.print()
    console.print("  [bold yellow]![/bold yellow]  %s" % msg)
    console.print()


def print_info(msg: str):
    console.print()
    console.print("  [bold blue]i[/bold blue]  %s" % msg)
    console.print()


def clear_screen():
    """Clear terminal screen."""
    console.clear()


def print_menu_table(vault_exists, key_count, is_unlocked):
    """Render the interactive main menu."""
    from .i18n import _t, lang
    from . import __version__

    clear_screen()

    # Header panel
    header = Table.grid(padding=(0, 1))
    header.add_column(style="bold cyan", min_width=20)
    header.add_column()
    header.add_row(_t("menu.title"), "[dim]%s[/dim]" % __version__)
    header.add_row("[dim]%s[/dim]" % _t("menu.subtitle"))

    console.print(Panel(header, box=box.DOUBLE, border_style="cyan", padding=(0, 2)))
    console.print()

    # Status bar
    if not vault_exists:
        status = "[bold red]%s[/bold red]" % _t("menu.status_no_vault")
    elif is_unlocked:
        status = "[bold green]%s[/bold green]" % _t("menu.status_ready")
    else:
        status = "[bold yellow]%s[/bold yellow]" % _t("menu.status_locked")

    status_text = _t("menu.vault_status", status=status, n=key_count, lang=lang.locale)
    console.print("  [dim]%s[/dim]" % status_text)
    console.print()

    # Menu items
    menu_items = [
        ("0", "menu.0.init", None),
        ("1", "menu.1.add", None),
        ("2", "menu.2.list", None),
        ("3", "menu.3.update", None),
        ("4", "menu.4.delete", None),
        ("5", "menu.5.passwd", None),
        ("6", "menu.6.settings", None),
    ]

    for num, i18n_key, _ in menu_items:
        label = _t(i18n_key)
        console.print("    [bold cyan]%s[/bold cyan]  %s" % (num, label))

    console.print()
    console.print("    [dim]q  %s[/dim]" % _t("menu.q.quit"))
    console.print()


def read_menu_choice():
    """Read a single menu choice from user. Returns the choice string."""
    from .i18n import _t
    while True:
        try:
            raw = input("  %s" % _t("menu.prompt")).strip().lower()
        except (EOFError, KeyboardInterrupt):
            return "q"
        if raw:
            return raw
