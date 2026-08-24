# extend-a-bot

Drop-in plugin tool groups for [Basic Bot](https://github.com/CablepunkPress/basic-bot) agents.

**To create an agent that uses these tools, start at
[build-a-bot](https://github.com/CablepunkPress/build-a-bot).**

## Installation

From your agent directory (after running `python build.py`):

```bash
python add_tools.py github
```

This copies the tool group into your `tools/` directory and installs
its pip dependencies. Follow the printed instructions to configure it.

## Available Tool Groups

| Group | Description |
|-------|-------------|
| `github` | GitHub repository tools via GitHub App — branches, PRs, file operations, commit history |

## Commands

```bash
python add_tools.py --list              # see available groups
python add_tools.py <group>             # install a group
python add_tools.py <group> --update    # update code, preserve config
python add_tools.py <group> --force     # overwrite everything
```

## Creating Tool Groups

A tool group is a directory containing:

| File | Purpose |
|------|---------|
| `tool.json` | Manifest — declares dependencies, secrets, and user config files |
| `_config.py` | User-editable values (owner, identity). Never overwritten by `--update`. |
| `_auth.py` | Shared logic (authentication, token caching). Importable by sibling tools. |
| `*.py` | Tool files — each defines a `TOOL` dict (schema) and a `handler` function. |

Files starting with `_` are shared modules, not registered as tools.
Tool files import siblings directly: `from _auth import auth_headers`.

See `github/` as the reference implementation.

### tool.json

```json
{
    "name": "github",
    "description": "GitHub repository tools via GitHub App",
    "version": "1.0.0",
    "dependencies": ["httpx", "pyjwt[crypto]"],
    "secrets": [
        {"service": "github-tools", "key": "github_app_id", "label": "GitHub App ID"}
    ],
    "config": [
        {"file": "_config.py", "name": "GITHUB_OWNER", "label": "GitHub org or username"}
    ],
    "trust": "read_write"
}
```

Consumers of the manifest:

- `add_tools.py` — installs packages listed in `dependencies`, prints next steps after install; `--update` protects files listed in `config`
- `add_secrets.py` — prompts for entries listed in `secrets`
- `trust` — reserved for future write confirmation gate

## License

MIT
