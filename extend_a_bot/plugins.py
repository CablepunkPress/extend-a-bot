"""Show, add, and remove an agent's tool groups.

The bountiful command calls these and passes what only it knows: the
built-in groups, and the folder of custom groups. A group is
added to an agent by naming it, with its settings, in agent.json. The
keys a group needs are asked for and stored in the system keyring
first, and if one isn't given, nothing is added. Removing a group
deletes its settings and keys together. A change takes effect the next
time the agent starts.
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
from basic_bot.tools import MANIFEST, MEMORY_GROUP, SETTINGS, custom_groups, offered_groups

from extend_a_bot.keys import KeyringUnavailable, delete_key, set_key

CUSTOM = "custom"


class PluginError(RuntimeError):
    """Something to tell the user. The message is user-facing."""


@dataclass(frozen=True)
class Group:
    """A tool group, as its tool.json describes it."""
    name: str
    source: str
    description: str
    sends: str
    keys: list[dict]
    folder: Path
    tools: list[str]

    def defaults(self) -> dict:
        """Return the settings a newly added group starts with."""
        path = self.folder / SETTINGS
        if not path.exists():
            return {}
        try:
            return tomllib.loads(path.read_text())
        except (OSError, tomllib.TOMLDecodeError) as e:
            raise PluginError(f"{path} couldn't be read: {e}") from e


def _read_group(folder: Path, source: str) -> Group:
    """Read a group's tool.json and the names of its tools."""
    try:
        data = json.loads((folder / MANIFEST).read_text())
    except (OSError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    return Group(
        name=folder.name,
        source=source,
        description=str(data.get("description", "")),
        sends=str(data.get("sends", "")),
        keys=[k for k in data.get("keys", []) if isinstance(k, dict) and k.get("name")],
        folder=folder,
        tools=sorted(f.stem for f in folder.glob("*.py") if not f.name.startswith("_")),
    )


def addable(custom_dir: Path | None) -> dict[str, Group]:
    """Return every group an agent can add. A custom group replaces an installed one."""
    groups = {
        name: _read_group(folder, source)
        for name, (folder, source) in offered_groups().items()
    }
    for name, folder in custom_groups(custom_dir).items():
        groups[name] = _read_group(folder, CUSTOM)
    return groups


def _memory() -> Group:
    """Return basic-bot's memory group."""
    return _read_group(MEMORY_GROUP, "basic-bot")


def _built_in(built_in: tuple[str, ...], groups: dict[str, Group]) -> list[Group]:
    """Return the built-in groups that are installed."""
    return [groups[name] for name in built_in if name in groups]


def _row(group: Group) -> tuple[str, str, str]:
    """Return a group's name, source, and tools, for listing."""
    return group.name, group.source, ", ".join(group.tools)


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

def _rows(rows: list[tuple[str, str, str]], columns: list[tuple[str, str, str]]) -> None:
    """Print rows of a name, a source, and tools, in columns sized to fit every row in columns."""
    name_width = max(len(r[0]) for r in columns) + 4
    source_width = max(len(r[1]) for r in columns) + 4
    for name, source, tools in rows:
        print(f"  {name:<{name_width}}{source:<{source_width}}{tools}")


def show_available(
    agents: list[tuple[str, Path]], built_in: tuple[str, ...], custom_dir: Path | None,
) -> None:
    """Print every tool group, where it comes from, and which agents have added it."""
    groups = addable(custom_dir)
    added = {agent_id: _added(path) for agent_id, path in agents}

    rest = [g for name, g in sorted(groups.items()) if name not in built_in]
    memory_rows = [_row(_memory())]
    built_in_rows = [_row(g) for g in _built_in(built_in, groups)]
    rest_rows = [_row(g) for g in rest]
    columns = memory_rows + built_in_rows + rest_rows

    print("Memory")
    _rows(memory_rows, columns)
    print("\nBuilt-in")
    if built_in_rows:
        _rows(built_in_rows, columns)
    else:
        print("  none")
    print("\nPlugins")
    if not rest:
        print("  none installed")
        return
    _rows(rest_rows, columns)
    for group in rest:
        users = [agent_id for agent_id in added if group.name in added[agent_id]]
        print()
        _say(f"{group.name}: {group.description}", indent=2)
        _say(f"used by: {', '.join(users) if users else 'no agent'}", indent=4)


def show_agent(
    agent_id: str, agent_path: Path, built_in: tuple[str, ...], custom_dir: Path | None,
) -> None:
    """Print every tool group one agent has, and where each comes from."""
    groups = addable(custom_dir)
    rows = [_row(_memory())] + [_row(g) for g in _built_in(built_in, groups)]
    for name in sorted(_added(agent_path)):
        if name in built_in:
            continue
        group = groups.get(name)
        if group is None:
            rows.append((name, "not installed", ""))
        else:
            rows.append((name, group.source, ", ".join(group.tools)))
    _rows(rows, rows)


# --- Adding and removing ---

def _refuse_built_in(name: str, built_in: tuple[str, ...]) -> None:
    if name == MEMORY_GROUP.name or name in built_in:
        raise PluginError(f"{name} is built in, so it can't be added or removed.")


def add(
    agent_id: str, agent_path: Path, name: str,
    built_in: tuple[str, ...], custom_dir: Path | None,
) -> None:
    """Add a tool group to an agent, or offer to replace its keys if it has the group."""
    _refuse_built_in(name, built_in)
    groups = {n: g for n, g in addable(custom_dir).items() if n not in built_in}
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


def remove(
    agent_id: str, agent_path: Path, name: str,
    built_in: tuple[str, ...], custom_dir: Path | None,
) -> None:
    """Remove a tool group from an agent, with its settings and keys."""
    _refuse_built_in(name, built_in)
    added = _added(agent_path)
    if name not in added:
        raise PluginError(f"{agent_id} doesn't have {name}.")

    group = addable(custom_dir).get(name)
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
