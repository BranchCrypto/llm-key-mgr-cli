"""Interactive main menu loop.

When the user runs `apikey-mgr` with no subcommand, this module
takes over and presents a numbered menu.  All heavy lifting is
delegated to the existing cmd_* functions from cli.py.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from .display import (
    console, print_menu_table, read_menu_choice,
    print_entries_table, print_entry_detail,
    print_success, print_error, print_warning, print_info,
)
from .input_util import prompt_text, prompt_confirm, prompt_password
from .models import KeyEntry, Protocol
from .vault import Vault
from .i18n import _t, lang


class InteractiveMenu:
    """Drives the interactive TUI menu loop."""

    def __init__(self, vault: Vault) -> None:
        self.vault = vault
        self.unlocked = False

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Enter the interactive menu loop."""
        while True:
            # Refresh state
            vault_exists = self.vault.exists
            key_count = 0
            if vault_exists and self.unlocked:
                try:
                    key_count = len(self.vault.list_entries())
                except Exception:
                    self.unlocked = False

            print_menu_table(vault_exists, key_count, self.unlocked)

            choice = read_menu_choice()

            if choice == "q":
                self._quit()
                break
            elif choice == "0":
                self._do_init()
            elif choice == "1":
                self._do_add()
            elif choice == "2":
                self._do_list()
            elif choice == "3":
                self._do_show()
            elif choice == "4":
                self._do_update()
            elif choice == "5":
                self._do_delete()
            elif choice == "6":
                self._do_passwd()
            elif choice == "7":
                self._do_export()
            elif choice == "8":
                self._do_import()
            elif choice == "9":
                self._do_lang()
            else:
                print_warning(_t("menu.invalid"))

            # Pause so user can read output before menu redraws
            self._pause()

    # ------------------------------------------------------------------
    # Vault helpers
    # ------------------------------------------------------------------

    def _ensure_vault(self) -> bool:
        if not self.vault.exists:
            print_error(_t("menu.no_vault_hint"))
            return False
        if not self.unlocked:
            if not self._do_unlock():
                return False
        return True

    def _do_unlock(self) -> bool:
        pw = prompt_password(_t("pw.master"))
        if self.vault.unlock(pw):
            self.unlocked = True
            return True
        print_error(_t("pw.incorrect"))
        return False

    def _pause(self):
        """Wait for user to press Enter before redrawing the menu."""
        try:
            input("\n  ...")
        except (EOFError, KeyboardInterrupt):
            pass

    def _quit(self):
        self.vault.close()
        print_info(_t("menu.goodbye"))

    # ------------------------------------------------------------------
    # Menu actions (delegate to vault / display)
    # ------------------------------------------------------------------

    def _do_init(self):
        from .cli import _do_language_selection

        v = self.vault
        if v.exists:
            print_warning(_t("vault.already_exists",
                             path="[dim]%s[/dim]" % v.db_path))
            if not prompt_confirm(_t("vault.overwrite"), default=False):
                print_info(_t("aborted"))
                return
            v.db_path.unlink(missing_ok=True)
            self.unlocked = False

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
        self.unlocked = True
        print_success(_t("init.created", path="[dim]%s[/dim]" % v.db_path))

    def _do_add(self):
        if not self._ensure_vault():
            return

        console.print()
        console.print("  [bold cyan]+ %s[/bold cyan]" % _t("add.title"))
        console.print()

        name = prompt_text(_t("add.name"), required=True)
        if self.vault.get_entry(name):
            print_error(_t("add.duplicate", name="[bold]'%s'[/bold]" % name))
            return

        protocol_str = prompt_text(_t("add.protocol") + " (OpenAI / Anthropic)", required=True)
        try:
            protocol = KeyEntry.parse_protocol(protocol_str)
        except KeyEntry.ProtocolError as e:
            print_error(_t("model.invalid_protocol", value=e.value))
            return

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
        self.vault.add_entry(entry, api_key)
        print_success(_t("add.success", name="[bold]'%s'[/bold]" % name))

    def _do_list(self):
        if not self._ensure_vault():
            return
        print_entries_table(self.vault.list_entries())

    def _do_show(self):
        if not self._ensure_vault():
            return
        entries = self.vault.list_entries()
        if not entries:
            print_warning(_t("list.empty"))
            return

        # Brief list with numbers
        console.print()
        for i, e in enumerate(entries, 1):
            console.print("    [bold cyan]%d[/bold cyan]  %s  (%s)" % (i, e.name, e.protocol.value))
        console.print()

        raw = input("  %s" % _t("menu.select_key")).strip()
        if raw.lower() == "q":
            return
        if not raw.isdigit():
            print_warning(_t("menu.invalid"))
            return
        idx = int(raw) - 1
        if idx < 0 or idx >= len(entries):
            print_warning(_t("menu.invalid"))
            return

        entry = entries[idx]

        reveal = False
        answer = input("  %s" % _t("menu.reveal_key")).strip().lower()
        if answer in ("y", "yes"):
            reveal = True

        if reveal:
            api_key_plain = self.vault.decrypt_api_key(entry)
            print_entry_detail(entry, api_key_plain)
            print_warning(_t("show.visible_warning"))
        else:
            print_entry_detail(entry)

    def _do_update(self):
        if not self._ensure_vault():
            return
        entries = self.vault.list_entries()
        if not entries:
            print_warning(_t("list.empty"))
            return

        console.print()
        for i, e in enumerate(entries, 1):
            console.print("    [bold cyan]%d[/bold cyan]  %s  (%s)" % (i, e.name, e.protocol.value))
        console.print()

        raw = input("  %s" % _t("menu.select_key")).strip()
        if raw.lower() == "q":
            return
        if not raw.isdigit():
            print_warning(_t("menu.invalid"))
            return
        idx = int(raw) - 1
        if idx < 0 or idx >= len(entries):
            print_warning(_t("menu.invalid"))
            return

        entry = entries[idx]
        name = entry.name

        console.print()
        console.print("  [bold cyan]* %s[/bold cyan]" % _t("update.title", name=name))
        console.print("  [dim]%s[/dim]" % _t("update.hint"))
        console.print()

        updates = {}

        new_name = prompt_text(_t("add.name"), default=entry.name)
        if new_name != entry.name:
            updates["new_name"] = new_name

        new_proto = prompt_text(_t("add.protocol"), default=entry.protocol.value)
        try:
            parsed = KeyEntry.parse_protocol(new_proto)
        except KeyEntry.ProtocolError as e:
            print_error(_t("model.invalid_protocol", value=e.value))
            return
        if parsed != entry.protocol:
            updates["protocol"] = parsed

        new_url = prompt_text(_t("add.base_url"), default=entry.base_url)
        if new_url != entry.base_url:
            updates["base_url"] = new_url

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

        self.vault.update_entry(name, **updates)
        display_name = updates.get("new_name", name)
        print_success(_t("update.success", name="[bold]'%s'[/bold]" % display_name))

    def _do_delete(self):
        if not self._ensure_vault():
            return
        entries = self.vault.list_entries()
        if not entries:
            print_warning(_t("list.empty"))
            return

        console.print()
        for i, e in enumerate(entries, 1):
            console.print("    [bold cyan]%d[/bold cyan]  %s  (%s)" % (i, e.name, e.protocol.value))
        console.print()

        raw = input("  %s" % _t("menu.select_key")).strip()
        if raw.lower() == "q":
            return
        if not raw.isdigit():
            print_warning(_t("menu.invalid"))
            return
        idx = int(raw) - 1
        if idx < 0 or idx >= len(entries):
            print_warning(_t("menu.invalid"))
            return

        entry = entries[idx]
        name = entry.name

        print_entry_detail(entry)

        if not prompt_confirm(
            _t("delete.confirm", name="[bold red]'%s'[/bold red]" % name),
            default=False,
        ):
            print_info(_t("aborted"))
            return
        if not prompt_confirm(_t("delete.sure"), default=False):
            print_info(_t("aborted"))
            return

        self.vault.delete_entry(name)
        print_success(_t("delete.success", name="[bold]'%s'[/bold]" % name))

    def _do_passwd(self):
        if not self.vault.exists:
            print_error(_t("menu.no_vault_hint"))
            return

        console.print()
        console.print("  [bold cyan]%s[/bold cyan]" % _t("pw.change_title"))
        console.print()

        old_pw = prompt_password(_t("pw.master_current"))
        if not self.vault.unlock(old_pw):
            print_error(_t("pw.incorrect"))
            return

        new_pw = prompt_password(_t("pw.master_new"), confirm=True)
        if len(new_pw) < 8:
            print_error(_t("init.pw_too_short", min_len=8))
            return

        if not self.vault.change_master_password(old_pw, new_pw):
            print_error(_t("pw.change_failed"))
            return

        self.unlocked = True
        print_success(_t("pw.changed"))

    def _do_export(self):
        if not self._ensure_vault():
            return

        from .crypto import generate_salt, encrypt_value, _derive_master_key
        import json
        from datetime import datetime

        export_pw = prompt_password(_t("export.pw"), confirm=True)
        if len(export_pw) < 4:
            print_error(_t("export.pw_too_short"))
            return

        entries = self.vault.list_entries()
        if not entries:
            print_warning(_t("export.empty"))
            return

        data = {"version": "1", "exported_at": datetime.now().isoformat(), "keys": []}
        for e in entries:
            data["keys"].append({
                "name": e.name, "protocol": e.protocol.value,
                "base_url": e.base_url, "model": e.model,
                "api_key_plaintext": self.vault.decrypt_api_key(e),
                "expires_at": e.expires_at, "notes": e.notes,
                "created_at": e.created_at, "updated_at": e.updated_at,
            })

        salt = generate_salt()
        ek = _derive_master_key(export_pw, salt)
        ct, iv, tag = encrypt_value(json.dumps(data, ensure_ascii=False), ek)
        default_path = "apikey_backup_%s.bin" % datetime.now().strftime("%Y%m%d_%H%M%S")

        custom = prompt_text(_t("menu.enter_path"), default=default_path)
        Path(custom).write_bytes(salt + iv + tag + ct)
        print_success(_t("export.success", n=len(entries), path="[bold]%s[/bold]" % custom))
        print_info(_t("export.keep_safe"))

    def _do_import(self):
        if not self._ensure_vault():
            return

        from .crypto import decrypt_value, _derive_master_key
        import json

        fpath = prompt_text(_t("menu.enter_path"), required=True)
        if not Path(fpath).exists():
            print_error(_t("import.not_found", path=fpath))
            return

        package = Path(fpath).read_bytes()
        if len(package) < 44:
            print_error(_t("import.invalid_file"))
            return

        salt, iv, tag, ct = package[:16], package[16:28], package[28:44], package[44:]
        export_pw = prompt_password(_t("import.pw"))
        try:
            json_str = decrypt_value(ct, iv, tag, _derive_master_key(export_pw, salt))
        except Exception:
            print_error(_t("import.decrypt_failed"))
            return

        data = json.loads(json_str)
        imported, skipped = 0, 0
        for kd in data.get("keys", []):
            name = kd["name"]
            if self.vault.get_entry(name):
                console.print("    [yellow]%s[/yellow]" % _t("import.skipping", name=name))
                skipped += 1
                continue
            pt_key = kd.get("api_key_plaintext", "")
            if not pt_key:
                console.print("    [yellow]%s[/yellow]" % _t("import.skipping_no_key", name=name))
                skipped += 1
                continue
            entry = KeyEntry(
                name=name, protocol=Protocol(kd["protocol"]),
                base_url=kd.get("base_url", ""), model=kd.get("model", ""),
                expires_at=kd.get("expires_at"), notes=kd.get("notes", ""),
                created_at=kd.get("created_at", ""), updated_at=kd.get("updated_at", ""),
            )
            try:
                self.vault.add_entry(entry, pt_key)
                console.print("    [green]+[/green] %s" % _t("import.imported", name=name))
                imported += 1
            except ValueError:
                skipped += 1

        console.print()
        print_success(_t("import.success", n=imported, m=skipped))

    def _do_lang(self):
        from .input_util import prompt_language

        console.print()
        new_locale = prompt_language()
        lang.set_locale(new_locale)
        lang.save_config()
        print_success(_t("lang.saved", lang=new_locale))
