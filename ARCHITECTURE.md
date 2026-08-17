# Architecture

extend-a-bot is a repository of plugin tool groups for Basic Bot
agents. It is not a Python package and is never installed via pip.
Agents pull tool groups from it via `add_tools.py`, which downloads
a tarball from GitHub and extracts the requested directory into the
agent's `tools/` folder.

## Design Principles

**Tool groups are self-contained.** Everything a group needs — auth
logic, configuration, tool files, manifest — lives in one directory.
Copy the directory to any agent and it works after filling in
`_config.py` and running `add_secrets.py`.

**User config is separated from maintainer code.** `_config.py` holds
values the user edits (org name, committer identity). Everything else
is maintainer-owned and safe to overwrite during `--update`.

**The manifest is the contract.** `tool.json` declares what the group
needs (pip packages, keyring secrets, user config files) so the
agent's scripts can discover requirements automatically.

## Repo Structure

```
extend-a-bot/
├── README.md
└── github/
    ├── tool.json
    ├── _config.py
    ├── _auth.py
    ├── create_branch.py
    ├── create_or_update_file.py
    ├── create_pull_request.py
    ├── delete_branch.py
    ├── delete_file.py
    ├── get_commit_history.py
    ├── get_repo_info.py
    ├── list_branches.py
    ├── list_repo_contents.py
    ├── list_repos.py
    ├── merge_pull_request.py
    └── read_file.py
```

Each top-level directory is a tool group. No nesting.

## How Groups Are Loaded

The engine's filesystem loader (`basic_bot/tools.py`) walks the
agent's `tools/` directory at startup:

1. For each subdirectory, temporarily adds it to `sys.path`
2. Loads `_` prefixed files as shared modules (not registered as tools)
3. Loads every other `.py` file; registers those with a `TOOL` dict
   and `handler` callable
4. Removes shared modules from `sys.modules` to prevent collisions
   between groups

Tool files import siblings directly (`from _auth import auth_headers`)
because the loader manages `sys.path` for them.

## How Groups Are Installed

`add_tools.py` in the agent repo downloads this repository as a
GitHub tarball, extracts the named directory into `tools/`, and
prints next steps from the manifest.

`--update` overwrites all files except those listed in `tool.json`'s
`config` section. If the new manifest introduces config files that
didn't exist before, they're installed and the user is told to
review them.

## Adding a New Tool Group

1. Create a directory at the repo root named for the group
2. Add `tool.json` with dependencies, secrets, and config declarations
3. Add `_config.py` with user-editable values (empty placeholders)
4. Add `_auth.py` or other shared modules as needed
5. Add tool files, each exporting `TOOL` (schema dict) and `handler`
6. Push to main — `add_tools.py --list` picks it up automatically
