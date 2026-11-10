"""Manage plugin tools: list them, add them to an agent, and remove them.

Plugins are the tool groups in extend-a-bot's tool_box/ and the
user's custom groups, which the bountiful command passes as a folder.
A custom group replaces a group of the same name from tool_box/. Only
plugins can be added or removed, and only plugins take keys.

A plugin is added to an agent by naming it, with its settings, in
agent.json. Its keys are asked for and stored in the system keyring
first, and if one isn't given, nothing is added. Removing a plugin
deletes its settings and keys together. A change takes effect the
next time the agent starts.
"""

import getpass
import shutil
import sys
import textwrap
import tomllib
from pathlib import Path

from basic_bot.agent import AgentError, load_agent, tool_groups, write_tools
from basic_bot.tools import MANIFEST, SETTINGS, Group, custom_groups, read_group

from extend_a_bot import TOOL_BOX
from extend_a_bot.keys import KeyringUnavailable, delete_key, set_key

SOURCE = "extend-a-bot"
CUSTOM = "custom"


class PluginError(RuntimeError):
    """Something to tell the user. The message is user-facing."""


def available(custom_dir: Path | None) -> dict[str, Group]:
    """Return every plugin an agent can add, by name."""
    groups = {
        folder.name: read_group(folder, SOURCE)
        for folder in sorted(TOOL_BOX.iterdir())
        if (folder / MANIFEST).exists()
    }
    for name, folder in custom_groups(custom_dir).items():
        groups[name] = read_group(folder, CUSTOM)
    return groups


def _defaults(group: Group) -> dict:
    """Return the settings a newly added plugin starts with."""
    path = group.folder / SETTINGS
    if not path.exists():
        return {}
    try:
        return tomllib.loads(path.read_text())
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise PluginError(f"{path} couldn't be read: {e}") from e


def _added(agent_path: Path) -> dict[str, dict]:
    try:
        return tool_groups(load_agent(agent_path))
    except AgentError as e:
        raise PluginError(str(e)) from e


def _say(text: str) -> None:
    """Print text wrapped to the terminal's width."""
    width = min(shutil.get_terminal_size().columns, 100)
    print(textwrap.fill(
        text, width=max(width, 40), break_on_hyphens=False, break_long_words=False,
    ))


# --- Adding and removing ---

def add(agent_id: str, agent_path: Path, name: str, custom_dir: Path | None) -> None:
    """Add a plugin to an agent, or offer to replace its keys if it has the plugin."""
    groups = available(custom_dir)
    if name not in groups:
        raise PluginError(
            f"There's no plugin called '{name}'. "
            f"Available: {', '.join(sorted(groups)) or 'none'}."
        )
    group = groups[name]
    added = _added(agent_path)

    if name in added:
        if not group.keys:
            print(f"{agent_id} already has {name}.")
            return
        _replace_keys(agent_id, group)
        return

    if group.sends:
        _say(group.sends)
        print()
    stored = _store_keys(agent_id, group)
    try:
        write_tools(agent_path, {**added, name: _defaults(group)})
    except (AgentError, PluginError):
        for key in stored:
            delete_key(agent_id, name, key)
        raise
    print(f"Added {name} to {agent_id}. It takes effect the next time {agent_id} starts.")


def remove(agent_id: str, agent_path: Path, name: str, custom_dir: Path | None) -> None:
    """Remove a plugin from an agent, with its settings and keys."""
    added = _added(agent_path)
    if name not in added:
        raise PluginError(f"{agent_id} doesn't have {name}.")

    group = available(custom_dir).get(name)
    if group:
        try:
            for key in group.keys:
                delete_key(agent_id, name, key["name"])
        except KeyringUnavailable as e:
            raise PluginError(str(e)) from e
    del added[name]
    try:
        write_tools(agent_path, added)
    except AgentError as e:
        raise PluginError(str(e)) from e

    note = " Its folder is untouched." if group and group.source == CUSTOM else ""
    print(f"Removed {name} from {agent_id}.{note} "
          f"It takes effect the next time {agent_id} starts.")


# --- Keys ---

def _store_keys(agent_id: str, group: Group) -> list[str]:
    """Ask for each of a group's keys and store it. Returns the names
    stored. A key not given stops everything, and what was stored is
    deleted, so a group is never added without its keys."""
    if not group.keys:
        return []
    if not sys.stdin.isatty():
        raise PluginError(f"{group.name} needs keys, so add it in a terminal.")

    stored: list[str] = []
    try:
        for key in group.keys:
            value = _read_key(key)
            if not value:
                for name in stored:
                    delete_key(agent_id, group.name, name)
                raise PluginError(
                    f"Nothing was added: {group.name} needs its {_label(key)}."
                )
            set_key(agent_id, group.name, key["name"], value)
            stored.append(key["name"])
    except KeyringUnavailable as e:
        raise PluginError(str(e)) from e
    return stored


def _replace_keys(agent_id: str, group: Group) -> None:
    if not sys.stdin.isatty():
        print(f"{agent_id} already has {group.name}.")
        return
    print(f"{agent_id} already has {group.name}.")
    try:
        for key in group.keys:
            answer = input(f"Replace its {_label(key)}? [y/N] ").strip().lower()
            if answer not in ("y", "yes"):
                continue
            value = _read_key(key)
            if value:
                set_key(agent_id, group.name, key["name"], value)
                print("Replaced.")
    except KeyringUnavailable as e:
        raise PluginError(str(e)) from e


def _label(key: dict) -> str:
    return str(key.get("label") or key["name"])


def _read_key(key: dict) -> str:
    """Ask for one key: pasted out of sight, or read from a file.

    A key that spans lines, such as a private key in a .pem file, is
    read from its file, since a hidden prompt takes only one line.
    """
    if key.get("from_file"):
        answer = input(f"The {_label(key)} file's path: ").strip()
        if not answer:
            return ""
        path = Path(answer.strip("'\"")).expanduser()
        try:
            return path.read_text().strip()
        except OSError as e:
            raise PluginError(f"Couldn't read {path}: {e.strerror}") from e
    return getpass.getpass(f"Paste the {_label(key)} (hidden): ").strip()
