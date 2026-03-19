# LLM Key Manager CLI

A production-grade terminal-based AI API key management tool with AES-256-GCM encryption, Argon2id key derivation, and bilingual (English/Chinese) interface.

## Features

- **Encrypted Storage** -- AES-256-GCM with Argon2id (OWASP 2024 parameters: 64 MiB, 3 passes, parallelism 4)
- **SQLite Backend** -- WAL mode for crash-safe atomic operations
- **CRUD Operations** -- Add, list, view, update, delete API keys
- **Interactive Menu** -- Run `llm-key-mgr` with no arguments to enter a full TUI menu
- **CLI Commands** -- Scriptable subcommands for automation
- **i18n** -- English and Chinese, auto-detected on first run, switchable anytime
- **Export / Import** -- Portable encrypted vault export; cross-vault import re-encrypts with target master key
- **Zero Leaks** -- API keys only decrypted on demand, never logged or displayed in full

## Quick Start

### Requirements

- Python >= 3.10
- pip

### Install

```bash
git clone https://github.com/BranchCrypto/llm-key-mgr-cli.git
cd llm-key-mgr-cli
pip install -e .
```

### First Run (Interactive Menu)

```bash
llm-key-mgr
```

On first launch you will be prompted to:
1. Choose your language (English / 中文)
2. Set a master password
3. Enter the interactive menu

### CLI Mode

```bash
# Initialize vault
llm-key-mgr init

# Add a key
llm-key-mgr add

# List all keys
llm-key-mgr list

# Show key details
llm-key-mgr show

# Update a key
llm-key-mgr update

# Delete a key
llm-key-mgr delete

# Change master password
llm-key-mgr passwd

# Export / Import
llm-key-mgr export -o my_keys.enc
llm-key-mgr import -i my_keys.enc

# Switch language
llm-key-mgr lang
llm-key-mgr --lang zh_CN list
```

## Commands

| Command | Description |
|---------|-------------|
| `llm-key-mgr` | Interactive menu (default) |
| `llm-key-mgr init` | Initialize a new encrypted vault |
| `llm-key-mgr add` | Add a new API key entry |
| `llm-key-mgr list` | List all stored keys |
| `llm-key-mgr show` | View a specific key's details |
| `llm-key-mgr update` | Update an existing key |
| `llm-key-mgr delete` | Delete a key |
| `llm-key-mgr passwd` | Change the master password |
| `llm-key-mgr export -o FILE` | Export vault to an encrypted file |
| `llm-key-mgr import -i FILE` | Import keys from an encrypted file |
| `llm-key-mgr lang` | Change interface language |

## Key Entry Fields

| Field | Description |
|-------|-------------|
| Name | A unique identifier for the key |
| Protocol | `OpenAI` or `Anthropic` |
| Base URL | API endpoint URL |
| Model | Model name (e.g. gpt-4, claude-3-opus) |
| API Key | The secret key (encrypted at rest) |
| Expiry | Optional expiry date (YYYY-MM-DD) |
| Notes | Free-form notes |

## Data Files

| File | Description |
|------|-------------|
| `~/.apikey_vault.db` | Encrypted SQLite vault |
| `~/.apikey_config.json` | Language preference |

## Security

- **Encryption**: AES-256-GCM (authenticated, tamper-evident)
- **Key Derivation**: Argon2id -- 64 MiB memory, 3 iterations, parallelism 4 (OWASP 2024 guidelines)
- **Password Hashing**: Argon2id with separate salt
- **API Key Display**: Keys are masked by default; full key only shown on explicit request
- **Export Safety**: Export files are independently encrypted with a user-provided password

## Development

### Run Tests

```bash
python test_e2e.py
```

### Project Structure

```
llm-key-mgr-cli/
  pyproject.toml
  README.md
  test_e2e.py
  src/
    llm_key_mgr_cli/
      __init__.py
      models.py        # Data models & validation
      crypto.py        # AES-256-GCM + Argon2id
      vault.py         # SQLite storage layer
      i18n.py          # Internationalization engine
      display.py       # Rich terminal display
      input_util.py    # Secure input helpers
      cli.py           # CLI commands
      menu.py          # Interactive TUI menu
      locales/
        en_US.json     # English strings
        zh_CN.json     # Chinese strings
```

## License

MIT
