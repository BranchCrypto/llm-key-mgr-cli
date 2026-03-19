"""E2E test with i18n support — non-interactive."""
import os, sys, json, tempfile, traceback
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from llm_key_mgr_cli.models import KeyEntry, Protocol
from llm_key_mgr_cli.crypto import encrypt_value, decrypt_value, generate_salt, _derive_master_key
from llm_key_mgr_cli.vault import Vault
from llm_key_mgr_cli.i18n import lang

log = []
PASS = "TestPass123!"

def fresh_vault(password=PASS):
    db = tempfile.mktemp(suffix=".db")
    v = Vault(db_path=db)
    v.init_vault(password)
    v.unlock(password)
    return v, db

def add_data(v):
    v.add_entry(KeyEntry(
        name="my-openai", protocol=Protocol.OPENAI,
        base_url="https://api.openai.com/v1", model="gpt-4o",
        expires_at="2026-12-31", notes="Production key",
    ), "sk-proj-abc123secret456")
    v.add_entry(KeyEntry(
        name="my-anthropic", protocol=Protocol.ANTHROPIC,
        base_url="https://api.anthropic.com", model="claude-3.5-sonnet",
        expires_at="2025-01-01", notes="Legacy key",
    ), "sk-ant-xyz789secret000")

def t01_i18n_basic():
    lang.set_locale("en_US")
    en_title = lang.t("add.title")
    assert "Add" in en_title or len(en_title) > 0, "en_US title: %s" % en_title
    lang.set_locale("zh_CN")
    zh_title = lang.t("add.title")
    assert len(zh_title) > 0, "zh_CN title empty"
    # Test fallback for missing key
    assert lang.t("nonexistent.key") == "nonexistent.key"
    # Test formatting
    result = lang.t("add.success", name="test")
    assert "test" in result
    log.append("PASS: i18n basic (en='%s', zh='%s', fallback, fmt)" % (en_title, zh_title))

def t02_i18n_detect():
    detected = lang.detect_system_locale()
    assert detected in lang.available
    log.append("PASS: i18n detect system locale -> %s" % detected)

def t03_init():
    db = tempfile.mktemp(suffix=".db")
    v = Vault(db_path=db)
    assert not v.exists
    v.init_vault(PASS)
    assert v.exists
    assert v.unlock(PASS)
    assert not v.unlock("wrong")
    v.close()
    os.unlink(db)
    log.append("PASS: Init vault")

def t04_add():
    v, db = fresh_vault()
    add_data(v)
    try:
        v.add_entry(KeyEntry(name="my-openai", protocol=Protocol.OPENAI, base_url="x"), "k")
        assert False
    except ValueError:
        pass
    # Test ProtocolError from models
    try:
        KeyEntry.parse_protocol("invalid")
        assert False
    except KeyEntry.ProtocolError:
        pass
    v.close()
    os.unlink(db)
    log.append("PASS: Add + duplicate + ProtocolError")

def t05_decrypt():
    v, db = fresh_vault()
    add_data(v)
    assert v.decrypt_api_key(v.get_entry("my-openai")) == "sk-proj-abc123secret456"
    v.close()
    os.unlink(db)
    log.append("PASS: Decrypt")

def t06_update():
    v, db = fresh_vault()
    add_data(v)
    u = v.update_entry("my-openai", model="gpt-4o-mini")
    assert u.model == "gpt-4o-mini"
    u = v.update_entry("my-openai", api_key_plaintext="newkey")
    assert v.decrypt_api_key(u) == "newkey"
    u = v.update_entry("my-openai", new_name="renamed")
    assert u.name == "renamed"
    # Test DateError
    try:
        KeyEntry.parse_date("not-a-date")
        assert False
    except KeyEntry.DateError:
        pass
    v.close()
    os.unlink(db)
    log.append("PASS: Update + DateError")

def t07_delete():
    v, db = fresh_vault()
    add_data(v)
    assert v.delete_entry("my-anthropic")
    assert len(v.list_entries()) == 1
    v.close()
    os.unlink(db)
    log.append("PASS: Delete")

def t08_passwd():
    v, db = fresh_vault()
    add_data(v)
    assert v.change_master_password(PASS, "NewPass456!")
    v.close()
    v2 = Vault(db_path=db)
    assert not v2.unlock(PASS)
    assert v2.unlock("NewPass456!")
    v2.close()
    os.unlink(db)
    log.append("PASS: Change master password")

def t09_export_import():
    v1, db1 = fresh_vault()
    add_data(v1)
    data = {"version": "1", "keys": [
        {"name": e.name, "protocol": e.protocol.value,
         "base_url": e.base_url, "model": e.model,
         "api_key_plaintext": v1.decrypt_api_key(e),
         "expires_at": e.expires_at, "notes": e.notes}
        for e in v1.list_entries()
    ]}
    v1.close()
    s = generate_salt()
    ct, iv, tag = encrypt_value(json.dumps(data), _derive_master_key("Bp1!", s))
    epath = tempfile.mktemp(suffix=".bin")
    Path(epath).write_bytes(s + iv + tag + ct)
    v2, db2 = fresh_vault("ImpVault1!")
    js = decrypt_value(Path(epath).read_bytes()[44:], Path(epath).read_bytes()[16:28],
                       Path(epath).read_bytes()[28:44], _derive_master_key("Bp1!", s))
    for kd in json.loads(js)["keys"]:
        v2.add_entry(KeyEntry(
            name=kd["name"], protocol=Protocol(kd["protocol"]),
            base_url=kd.get("base_url",""), model=kd.get("model",""),
            expires_at=kd.get("expires_at"), notes=kd.get("notes",""),
        ), kd["api_key_plaintext"])
    assert len(v2.list_entries()) == 2
    assert v2.decrypt_api_key(v2.get_entry("my-openai")) == "sk-proj-abc123secret456"
    v2.close()
    os.unlink(epath); os.unlink(db1); os.unlink(db2)
    log.append("PASS: Export + cross-vault import")

for fn in [t01_i18n_basic, t02_i18n_detect, t03_init, t04_add, t05_decrypt,
           t06_update, t07_delete, t08_passwd, t09_export_import]:
    try:
        fn()
    except Exception as e:
        log.append("FAIL: %s -- %s" % (fn.__name__, e))
        log.append(traceback.format_exc())

out = "\n".join(["="*60, "  LLM Key Manager CLI + i18n - E2E Tests", "="*60] + log)
passed = sum(1 for l in log if l.startswith("PASS"))
failed = sum(1 for l in log if l.startswith("FAIL"))
out += "\n\n  Result: %d passed, %d failed\n" % (passed, failed) + "="*60
Path(r"C:\Users\Administrator\apikey-manager\test_results.txt").write_text(out, encoding="utf-8")
