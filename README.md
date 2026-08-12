# extend-a-bot

Drop-in tool groups for Basic Bot agents.

## Installation

From your agent directory:

python add_tool.py github

This copies the tool group into your `tools/` directory.
Then follow the printed instructions to configure it.

## Available tool groups

| Group | Description |
|-------|-------------|
| `github` | GitHub repository tools via GitHub App — branches, PRs, file operations |

## Creating tool groups

A tool group is a directory with:

- `tool.json` — manifest declaring dependencies, secrets, and config
- `_auth.py` (optional) — shared code, not loaded as a tool
- `*.py` — tool files, each with a `TOOL` dict and a `handler` function

See `github/` as the reference implementation.
