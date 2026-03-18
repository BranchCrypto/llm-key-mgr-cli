"""CLI interface -- the main entry point for apikey-mgr."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from . import __version__
from .display import (
    console, print_entries_table, print_entry_detail,
    print_success, print_error, print_warning, print_info,
)
from .input_util import (
    prompt_password, prompt_text, prompt_choice,
    prompt_confirm, prompt_language,
)
from .models import KeyEntry, Protocol
from .vault import Vault
from .crypto import generate_salt, encrypt_value, decrypt_value, _derive_master_key
from .i18n import lang, _t

_vault: Optional[Vault] = None


def _get_vault() -> Vault:
    global _vault
    if _vault is None:
        _vault = Vault()
    return _vault


def _require_vault() -> Vault:
    v = _get_vault()
    if not v.exists:
        print_error(_t("vault.not_found", cmd="[cyan]apikey-mgr init[/cyan]"))
        sys.exit(1)
    return v


def _unlock_vault(vault, password=None):
    if password is None:
        password = prompt_password(_t("pw.master"))
    if not vault.unlock(password):
        print_error(_t("pw.incorrect"))
        return False
    return True


def cmd_lang(args):
    """Show current language or interactively change it."""
    console.print()
    if args.code:
        code = args.code
        if code not in lang.available:
            print_error(_t("prompt.choose_from", choices=", ".join(lang.available)))
            return
        lang.set_locale(code)
        lang.save_config()
        print_success(_t("lang.saved", lang=code))
        return
    new_locale = prompt_language()
    if new_locale != lang.locale:
        lang.set_locale(new_locale)
        lang.save_config()
        print_success(_t("lang.saved", lang=new_locale))
    else:
        print_info(_t("lang.saved", lang=new_locale))


def _do_language_selection():
    """Interactive language selection shown during init. Returns locale code."""
    console.print()
    console.print("  [bold cyan]%s[/bold cyan]" % _t("lang.select"))
    console.print()
    detected = lang.detect_system_locale()
    console.print("  [dim]%s[/dim]" % _t("lang.detected", locale=detected))
    console.print()
    names = lang.lang_names
    codes = lang.available
    for i, code in enumerate(codes, 1):
        marker = " [dim]<--[/dim]" if code == detected else ""
        console.print("    [bold]%d[/bold]  %s  (%s)%s" % (i, code, names[code], marker))
    console.print()
    while True:
        try:
            raw = input("  > ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print()
            raise
        selected = None
        if not raw:
            selected = detected
        elif raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(codes):
                selected = codes[idx]
        elif raw in codes:
            selected = raw
        if selected:
            break
        print_warning(_t("prompt.choose_from", choices=", ".join(str(i+1) for i in range(len(codes)))))
    return selected


def cmd_init(args):
    """Initialize a new vault."""
    v = _get_vault()
    if v.exists:
        print_warning(_t("vault.already_exists", path="[dim]%s[/dim]" % v.db_path))
        if not prompt_confirm(_t("vault.overwrite"), default=False):
            print_info(_t("aborted"))
            return
        v.db_path.unlink(missing_ok=True)
    selected = _do_language_selection()
    lang.set_locale(selected)
    lang.save_config()
    print_success(_t("lang.saved", lang=selected))
    console.print()
    console.print("  [bold cyan]%s[/bold cyan]" % _t("init.title"))
    console.print("  [dim]%s[/dim]" % _t("init.hint"))
    console.print()
    password = prompt_password(_t("pw.master"), confirm=True)
    if len(password) < 8:
        print_error(_t("init.pw_too_short", min_len=8))
        return
    v.init_vault(password)
    print_success(_t("init.created", path="[dim]%s[/dim]" % v.db_path))
    print_info(_t("init.next_step", cmd="[cyan]apikey-mgr add[/cyan]"))


def cmd_add(args):
    """Add a new API key entry."""
    v = _require_vault()
    if not _unlock_vault(v):
        return
    console.print()
    console.print("  [bold cyan]+ %s[/bold cyan]" % _t("add.title"))
    console.print()
    name = prompt_text(_t("add.name"), required=True)
    if v.get_entry(name):
        print_error(_t("add.duplicate", name="[bold]'%s'[/bold]" % name))
        return
    protocol_str = prompt_choice(_t("add.protocol"), ["OpenAI", "Anthropic"])
    protocol = Protocol.parse_protocol(protocol_str)
    base_url = prompt_text(_t("add.base_url"), required=True)
    model = prompt_text(_t("add.model"), default="")
    api_key = prompt_password(_t("add.api_key"))
    if not api_key:
        print_error(_t("add.api_key_required"))
        return
    expires_at_raw = prompt_text(_t("add.expiry"), default="")
    try:
        expires_at = KeyEntry.parse_date(expires_at_raw)
    except KeyEntry.DateError as e:
        print_error(_t("model.invalid_date", value=e.value))
        return
    notes = prompt_text(_t("add.notes"), default="")
    entry = KeyEntry(
        name=name, protocol=protocol, base_url=base_url,
        model=model, expires_at=expires_at, notes=notes,
    )
    v.add_entry(entry, api_key)
    print_success(_t("add.success", name="[bold]'%s'[/bold]" % name))


def cmd_list(args):
    """List all stored API keys."""
    v = _require_vault()
    if not _unlock_vault(v):
        return
    print_entries_table(v.list_entries())


def cmd_show(args):
    """Show details of a specific key."""
    v = _require_vault()
    if not _unlock_vault(v):
        return
    entry = v.get_entry(args.name)
    if not entry:
        print_error(_t("delete.not_found", name="[bold]'%s'[/bold]" % args.name))
        return
    api_key_plain = None
    if args.reveal:
        console.print()
        if not prompt_confirm(
            _t("show.reveal_confirm", name="[bold]'%s'[/bold]" % args.name),
            default=False,
        ):
            print_info(_t("show.masked"))
        else:
            api_key_plain = v.decrypt_api_key(entry)
            print_entry_detail(entry, api_key_plain)
            print_warning(_t("show.visible_warning"))
            return
    print_entry_detail(entry, api_key_plain)


def cmd_update(args):
    """Update fields of an existing key."""
    v = _require_vault()
    if not _unlock_vault(v):
        return
    entry = v.get_entry(args.name)
    if not entry:
        print_error(_t("delete.not_found", name="[bold]'%s'[/bold]" % args.name))
        return
    console.print()
    console.print("  [bold cyan]* %s[/bold cyan]" % _t("update.title", name=args.name))
    console.print("  [dim]%s[/dim]" % _t("update.hint"))
    console.print()
    updates = {}
    new_name = prompt_text(_t("add.name"), default=entry.name)
    if new_name != entry.name:
        updates["new_name"] = new_name
    protocol_str = prompt_choice(_t("add.protocol"), ["OpenAI", "Anthropic"], default=entry.protocol.value)
    new_protocol = Protocol.parse_protocol(protocol_str)
    if new_protocol != entry.protocol:
        updates["protocol"] = new_protocol
    new_base_url = prompt_text(_t("add.base_url"), default=entry.base_url)
    if new_base_url != entry.base_url:
        updates["base_url"] = new_base_url
    new_model = prompt_text(_t("add.model"), default=entry.model)
    if new_model != entry.model:
        updates["model"] = new_model
    if prompt_confirm(_t("update.change_key"), default=False):
        new_key = prompt_password(_t("update.new_api_key"))
        if new_key:
            updates["api_key_plaintext"] = new_key
    current_exp = entry.expires_at if entry.expires_at else _t("never")
    new_exp_raw = prompt_text(_t("update.expiry_date"), default=current_exp)
    try:
        new_exp = KeyEntry.parse_date(new_exp_raw)
    except KeyEntry.DateError as e:
        print_error(_t("model.invalid_date", value=e.value))
        return
    if new_exp != entry.expires_at:
        updates["expires_at"] = new_exp
    new_notes = prompt_text(_t("add.notes"), default=entry.notes)
    if new_notes != entry.notes:
        updates["notes"] = new_notes
    if not updates:
        print_info(_t("update.no_changes"))
        return
    display_name = updates.get("new_name", args.name)
    print_success(_t("update.success", name="[bold]'%s'[/bold]" % display_name))


def cmd_delete(args):
    """Delete an API key entry."""
    v = _require_vault()
    if not _unlock_vault(v):
        return
    entry = v.get_entry(args.name)
    if not entry:
        print_error(_t("delete.not_found", name="[bold]'%s'[/bold]" % args.name))
        return
    print_entry_detail(entry)
    if not prompt_confirm(_t("delete.confirm", name="[bold red]'%s'[/bold red]" % args.name), default=False):
        print_info(_t("aborted"))
        return
    if not prompt_confirm(_t("delete.sure"), default=False):
        print_info(_t("aborted"))
        return
    v.delete_entry(args.name)
    print_success(_t("delete.success", name="[bold]'%s'[/bold]" % args.name))


def cmd_passwd(args):
    """Change the master password."""
    v = _require_vault()
    console.print()
    console.print("  [bold cyan]%s[/bold cyan]" % _t("pw.change_title"))
    console.print()
    old_pw = prompt_password(_t("pw.master_current"))
    if not v.unlock(old_pw):
        print_error(_t("pw.incorrect"))
        return
    new_pw = prompt_password(_t("pw.master_new"), confirm=True)
    if len(new_pw) < 8:
        print_error(_t("init.pw_too_short", min_len=8))
        return
    if not v.change_master_password(old_pw, new_pw):
        print_error(_t("pw.change_failed"))
        return
    print_success(_t("pw.changed"))


def cmd_export(args):
    """Export all keys as an encrypted backup file."""
    v = _require_vault()
    if not _unlock_vault(v):
        return
    export_pw = prompt_password(_t("export.pw"), confirm=True)
    if len(export_pw) < 4:
        print_error(_t("export.pw_too_short"))
        return
    entries = v.list_entries()
    if not entries:
        print_warning(_t("export.empty"))
        return
    data = {"version": "1", "exported_at": datetime.now().isoformat(), "keys": []}
    for e in entries:
        data["keys"].append({
            "name": e.name, "protocol": e.protocol.value,
            "base_url": e.base_url, "model": e.model,
            "api_key_plaintext": v.decrypt_api_key(e),
            "expires_at": e.expires_at, "notes": e.notes,
            "created_at": e.created_at, "updated_at": e.updated_at,
        })
    salt = generate_salt()
    export_key = _derive_master_key(export_pw, salt)
    ct, iv, tag = encrypt_value(json.dumps(data, ensure_ascii=False), export_key)
    package = salt + iv + tag + ct
    default_path = "apikey_backup_%s.bin" % datetime.now().strftime("%Y%m%d_%H%M%S")
    export_path = args.path if args.path else default_path
    Path(export_path).write_bytes(package)
    print_success(_t("export.success", n=len(entries), path="[bold]%s[/bold]" % export_path))
    print_info(_t("export.keep_safe"))


def cmd_import(args):
    """Import keys from an encrypted backup file."""
    v = _require_vault()
    if not _unlock_vault(v):
        return
    import_path = args.path
    if not Path(import_path).exists():
        print_error(_t("import.not_found", path=import_path))
        return
    package = Path(import_path).read_bytes()
    if len(package) < 44:
        print_error(_t("import.invalid_file"))
        return
    salt, iv, tag, ct = package[:16], package[16:28], package[28:44], package[44:]
    export_pw = prompt_password(_t("import.pw"))
    export_key = _derive_master_key(export_pw, salt)
    try:
        json_str = decrypt_value(ct, iv, tag, export_key)
    except Exception:
        print_error(_t("import.decrypt_failed"))
        return
    data = json.loads(json_str)
    imported, skipped = 0, 0
    for key_data in data.get("keys", []):
        name = key_data["name"]
        if v.get_entry(name):
            console.print("    [yellow]%s[/yellow]" % _t("import.skipping", name=name))
            skipped += 1
            continue
        entry = KeyEntry(
            name=name, protocol=Protocol(key_data["protocol"]),
            base_url=key_data.get("base_url", ""), model=key_data.get("model", ""),
            expires_at=key_data.get("expires_at"), notes=key_data.get("notes", ""),
            created_at=key_data.get("created_at", ""), updated_at=key_data.get("updated_at", ""),
        )
        plaintext_key = key_data.get("api_key_plaintext", "")
        if not plaintext_key:
            console.print("    [yellow]%s[/yellow]" % _t("import.skipping_no_key", name=name))
            skipped += 1
            continue
        try:
            v.add_entry(entry, plaintext_key)
            console.print("    [green]+[/green] %s" % _t("import.imported", name=name))
            imported += 1
        except ValueError:
            skipped += 1
    console.print()
    print_success(_t("import.success", n=imported, m=skipped))


def build_parser():
    parser = argparse.ArgumentParser(
        prog="apikey-mgr",
        description="AI API Key Manager -- encrypted key storage for the terminal",
    )
    parser.add_argument("-V", "--version", action="version", version="%(prog)s " + __version__)
    parser.add_argument("--lang", type=str, default=None,
                        help="Override language for this session (e.g. zh_CN, en_US)")
    parser.add_argument("--db", type=str, default=None, help="Custom database path")
    sub = parser.add_subparsers(dest="command", help="Command to run")
    sub.add_parser("init", help="Create a new encrypted vault")
    sub.add_parser("add", help="Add a new API key")
    sub.add_parser("list", help="List all stored API keys")
    p_show = sub.add_parser("show", help="Show details of a specific key")
    p_show.add_argument("name", help="Name of the key to show")
    p_show.add_argument("--reveal", action="store_true", help="Reveal the full API key")
    p_update = sub.add_parser("update", help="Update fields of an existing key")
    p_update.add_argument("name", help="Name of the key to update")
    p_del = sub.add_parser("delete", help="Delete an API key")
    p_del.add_argument("name", help="Name of the key to delete")
    sub.add_parser("passwd", help="Change the master password")
    p_export = sub.add_parser("export", help="Export all keys as encrypted backup")
    p_export.add_argument("--path", type=str, default=None, help="Output file path")
    p_import = sub.add_parser("import", help="Import keys from encrypted backup")
    p_import.add_argument("path", help="Path to the backup file")
    p_lang = sub.add_parser("lang", help="Show or change language setting")
    p_lang.add_argument("code", nargs="?", default=None, help="Locale code (e.g. zh_CN)")
    return parser


def main(argv=None):
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    # Load persisted language before parsing (needed for --lang override)
    saved = lang.load_config()
    if saved:
        lang.set_locale(saved)
    parser = build_parser()
    args = parser.parse_args(argv)
    # --lang flag overrides persisted setting
    if args.lang:
        lang.set_locale(args.lang)
    if not args.command:
        from .menu import InteractiveMenu
        InteractiveMenu(_get_vault()).run()
        return
    if args.db:
        global _vault
        _vault = Vault(db_path=args.db)
    commands = {
        "init": cmd_init, "add": cmd_add, "list": cmd_list,
        "show": cmd_show, "update": cmd_update, "delete": cmd_delete,
        "passwd": cmd_passwd, "export": cmd_export, "import": cmd_import,
        "lang": cmd_lang,
    }
    handler = commands.get(args.command)
    if handler:
        try:
            handler(args)
        except KeyboardInterrupt:
            console.print("\n[dim]%s[/dim]" % _t("interrupted"))
        finally:
            _get_vault().close()
    else:
        parser.print_help()
