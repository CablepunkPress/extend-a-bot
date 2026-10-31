"""Adding and removing an agent's tool groups.

The bountiful command calls these, passing the agent's id and folder;
they do the work and print what happened, so the command only routes.

A tool group is a plugin, from this package's tool_box/, or custom,
the user's own folder in the agent's tools/. Either is added to an
agent by naming it in the "tools" section of the agent's agent.json,
with its settings, and a custom folder of the same name as a plugin
takes its place. A group is never added half way: keys it needs are
asked for and stored first, and if one isn't given, nothing is added.
Removing a group deletes its settings and its keys together. Keys live
in the system keyring under the agent's id (keys.py). A change takes
effect the next time the agent starts.
"""

import getpass
import json
import shutil
import sys
import textwrap
import tomllib
from dataclasses import dataclass
from pathlib import Path

from basic_bot.agent import AgentError, load_agent, tool_groups, write_tools
from basic_bot.tools import MANIFEST, custom_groups

from extend_a_bot import TOOL_BOX
from extend_a_bot.keys import KeyringUnavailable, delete_key, set_key

DEFAULTS = "settings.toml"


class PluginError(RuntimeError):
    """Something to tell the user. The message is user-facing."""


@dataclass(frozen=True)
class Group:
    """A tool group, as its manifest describes it."""
    name: str
    kind: str
    description: str
    sends: str
    keys: list[dict]
    folder: Path

    def defaults(self) -> dict:
        """The settings a newly added group starts with."""
        path = self.folder / DEFAULTS
        if not path.exists():
            return {}
        try:
            return tomllib.loads(path.read_text())
        except (OSError, tomllib.TOMLDecodeError) as e:
            raise PluginError(f"{path} couldn't be read: {e}") from e


def _read_group(folder: Path, kind: str) -> Group:
    try:
        data = json.loads((folder / MANIFEST).read_text())
    except (OSError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    return Group(
        name=folder.name,
        kind=kind,
        description=str(data.get("description", "")),
        sends=str(data.get("sends", "")),
        keys=[k for k in data.get("keys", []) if isinstance(k, dict) and k.get("name")],
        folder=folder,
    )


def plugins() -> dict[str, Group]:
    """Every plugin tool group in this package, by name."""
    return {
        folder.name: _read_group(folder, "plugin")
        for folder in sorted(TOOL_BOX.iterdir())
        if (folder / MANIFEST).exists()
    }


def _groups_for(agent_path: Path) -> dict[str, Group]:
    """The groups this agent could add: plugins, with its custom groups
    taking the place of any plugin of the same name."""
    groups = plugins()
    for name, folder in custom_groups(agent_path).items():
        groups[name] = _read_group(folder, "custom")
    return groups


def _added(agent_path: Path) -> dict[str, dict]:
    try:
        return tool_groups(load_agent(agent_path))
    except AgentError as e:
        raise PluginError(str(e)) from e


def _say(text: str, indent: int = 0) -> None:
    """Print text wrapped to the terminal's width, every line indented.

    The descriptions here are for people, from each group's tool.json;
    the model reads the TOOL descriptions in the tools themselves.
    """
    width = min(shutil.get_terminal_size().columns, 100)
    pad = " " * indent
    print(textwrap.fill(
        text, width=max(width, 40), initial_indent=pad, subsequent_indent=pad,
        break_on_hyphens=False, break_long_words=False,
    ))


def _tilde(path: Path) -> str:
    """A path with the home folder written as ~."""
    try:
        return "~/" + str(path.relative_to(Path.home()))
    except ValueError:
        return str(path)


# --- Showing ---

def show_available(agents: list[tuple[str, Path]]) -> None:
    """bountiful tools: the plugins, which agents use each, and any
    custom groups in the agents' folders."""
    available = plugins()
    added = {agent_id: _added(path) for agent_id, path in agents}
    custom = {agent_id: custom_groups(path) for agent_id, path in agents}

    print("Plugin tools")
    if not available:
        print("  none installed")
    for group in available.values():
        users = [
            agent_id for agent_id in added
            if group.name in added[agent_id] and group.name not in custom[agent_id]
        ]
        print(f"  {group.name}")
        _say(group.description, indent=6)
        _say(f"used by: {', '.join(users) if users else 'no agent'}", indent=6)

    found = [
        (name, agent_id, name in added[agent_id])
        for agent_id in custom
        for name in custom[agent_id]
    ]
    if found:
        print("\nCustom tools")
        for name, agent_id, on in sorted(found):
            print(f"  {name}  in {agent_id}'s tools/{'' if on else ', not added'}")


def show_agent(agent_id: str, agent_path: Path) -> None:
    """bountiful tools ID: the groups this agent has added."""
    added = _added(agent_path)
    if not added:
        print(f"{agent_id} has only the default tools.")
        return
    groups = _groups_for(agent_path)
    width = max(len(name) for name in added) + 4
    for name in sorted(added):
        kind = groups[name].kind if name in groups else "not installed"
        print(f"  {name:<{width}}{kind}")


# --- Adding and removing ---

def add(agent_id: str, agent_path: Path, name: str) -> None:
    """bountiful add GROUP ID: add a tool group to an agent.

    Run again on a group the agent has, it offers to replace the
    group's keys.
    """
    groups = _groups_for(agent_path)
    if name not in groups:
        raise PluginError(
            f"There's no tool group called '{name}'. "
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
        write_tools(agent_path, {**added, name: group.defaults()})
    except (AgentError, PluginError):
        for key in stored:
            delete_key(agent_id, name, key)
        raise
    print(f"Added {name} to {agent_id}. It takes effect the next time {agent_id} starts.")


def remove(agent_id: str, agent_path: Path, name: str) -> None:
    """bountiful remove GROUP ID: remove a tool group, with its settings
    and keys. A custom group's folder is left as it is."""
    added = _added(agent_path)
    if name not in added:
        raise PluginError(f"{agent_id} doesn't have {name}.")

    group = _groups_for(agent_path).get(name)
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

    note = " Its folder is untouched." if group and group.kind == "custom" else ""
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
