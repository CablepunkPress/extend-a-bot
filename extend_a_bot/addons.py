"""Turning tool groups on and off for one agent, and storing its keys.

The bountiful command calls these, passing the agent's id and folder;
they do the work and print what happened, so the command only routes.
Nothing here imports basic-bot: an agent's tools/ folder and its id
are all it needs.

An agent uses a curated group when its tools/ folder holds a settings
file named for it, tools/<group>.toml, copied from the group's
settings.toml. Turning a group off renames that file to
<group>.toml.off, so the agent's settings come back if it's turned on
again. Keys live in the system keyring under the agent's id (keys.py).
A change takes effect the next time the agent starts.
"""

import getpass
import json
import shutil
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

from extend_a_bot import TOOL_BOX
from extend_a_bot.keys import KeyringUnavailable, delete_key, get_key, set_key

MANIFEST = "tool.json"
TEMPLATE = "settings.toml"
SETTINGS = ".toml"
OFF = ".toml.off"


class AddonError(RuntimeError):
    """Something to tell the user. The message is user-facing."""


@dataclass(frozen=True)
class Group:
    """A curated tool group, as its manifest describes it."""
    name: str
    description: str
    sends: str
    keys: list[dict]
    required_settings: list[str]
    folder: Path


# --- Reading ---

def available() -> dict[str, Group]:
    """Every curated tool group in this package, by name."""
    groups = {}
    for folder in sorted(TOOL_BOX.iterdir()):
        manifest = folder / MANIFEST
        if not manifest.exists():
            continue
        data = json.loads(manifest.read_text())
        groups[folder.name] = Group(
            name=folder.name,
            description=data.get("description", ""),
            sends=data.get("sends", ""),
            keys=data.get("keys", []),
            required_settings=data.get("required_settings", []),
            folder=folder,
        )
    return groups


def _group(name: str) -> Group:
    groups = available()
    if name not in groups:
        raise AddonError(
            f"There's no tool group called '{name}'. "
            f"Available: {', '.join(groups) or 'none'}."
        )
    return groups[name]


def uses(agent_path: Path, group: str) -> bool:
    """Whether the agent has this curated group turned on."""
    return (agent_path / "tools" / f"{group}{SETTINGS}").exists()


def _own_folder(agent_path: Path, group: str) -> bool:
    return (agent_path / "tools" / group / MANIFEST).exists()


def missing_settings(agent_path: Path, group: Group) -> list[str]:
    """Required settings the agent hasn't filled in."""
    path = agent_path / "tools" / f"{group.name}{SETTINGS}"
    try:
        settings = tomllib.loads(path.read_text())
    except (OSError, tomllib.TOMLDecodeError):
        return list(group.required_settings)
    return [s for s in group.required_settings if not settings.get(s)]


def missing_keys(agent_id: str, group: Group) -> list[str]:
    """Labels of the keys the agent doesn't have stored."""
    return [
        k["label"] for k in group.keys
        if not get_key(agent_id, group.name, k["name"])
    ]


def _problems(agent_id: str, agent_path: Path, group: Group) -> list[str]:
    """What stands between a group and working, in words."""
    problems = []
    settings = missing_settings(agent_path, group)
    if settings:
        problems.append(
            f"settings to fill in, in {_tilde(agent_path / 'tools' / (group.name + SETTINGS))}: "
            + ", ".join(settings)
        )
    try:
        keys = missing_keys(agent_id, group)
    except KeyringUnavailable as e:
        problems.append(str(e))
    else:
        if keys:
            problems.append(
                f"keys to store, with 'bountiful keys {agent_id} {group.name}': "
                + ", ".join(keys)
            )
    return problems


def _tilde(path: Path) -> str:
    """A path with the home folder written as ~."""
    try:
        return "~/" + str(path.relative_to(Path.home()))
    except ValueError:
        return str(path)


# --- Commands ---

def show_available(agents: list[tuple[str, Path]]) -> None:
    """bountiful tools: every group, and which agents use it."""
    groups = available()
    if not groups:
        print("No tool groups are installed.")
        return
    for group in groups.values():
        users = [agent_id for agent_id, path in agents if uses(path, group.name)]
        print(f"  {group.name}")
        print(f"      {group.description}")
        print(f"      used by: {', '.join(users) if users else 'no agent'}")
    print("\nTurn one on for an agent with: bountiful add <agent> <group>")


def show_agent(agent_id: str, agent_path: Path) -> None:
    """bountiful tools <agent>: the agent's groups, and what each lacks."""
    groups = available()
    tools_dir = agent_path / "tools"
    found = False

    for group in groups.values():
        if not uses(agent_path, group.name) or _own_folder(agent_path, group.name):
            continue
        found = True
        problems = _problems(agent_id, agent_path, group)
        print(f"  {group.name}  {'ready' if not problems else 'needs:'}")
        for problem in problems:
            print(f"      {problem}")

    if tools_dir.is_dir():
        for folder in sorted(tools_dir.iterdir()):
            if (folder / MANIFEST).exists():
                found = True
                note = " (in place of the curated group)" if folder.name in groups else ""
                print(f"  {folder.name}  your own{note}")

    if not found:
        print(f"{agent_id} has no tool groups beyond the ones every agent has.")
        print("'bountiful tools' lists what's available.")


def add(agent_id: str, agent_path: Path, name: str) -> None:
    """bountiful add <agent> <group>: turn a curated group on."""
    group = _group(name)
    tools_dir = agent_path / "tools"
    settings = tools_dir / f"{name}{SETTINGS}"
    kept = tools_dir / f"{name}{OFF}"

    if _own_folder(agent_path, name):
        raise AddonError(
            f"{agent_id} has its own tools/{name}/ folder, which takes the "
            f"place of the curated {name} group. Rename or remove that folder "
            f"to use the curated one."
        )
    if settings.exists():
        print(f"{name} is already on for {agent_id}.")
    else:
        tools_dir.mkdir(parents=True, exist_ok=True)
        if kept.exists():
            kept.rename(settings)
            print(f"{name} is on again for {agent_id}, with its earlier settings.")
        else:
            shutil.copyfile(group.folder / TEMPLATE, settings)
            print(f"{name} is on for {agent_id}.")

    if group.sends:
        print(f"\n{group.sends}")

    problems = _problems(agent_id, agent_path, group)
    if problems:
        print("\nBefore it works, it needs:")
        for problem in problems:
            print(f"  - {problem}")
    print(f"\nIt takes effect the next time {agent_id} starts.")


def remove(agent_id: str, agent_path: Path, name: str) -> None:
    """bountiful remove <agent> <group>: turn a curated group off.

    The settings file is kept beside it as <group>.toml.off, so turning
    the group on again brings the settings back. Keys stay stored.
    """
    tools_dir = agent_path / "tools"
    settings = tools_dir / f"{name}{SETTINGS}"
    if not settings.exists():
        if _own_folder(agent_path, name):
            raise AddonError(
                f"tools/{name}/ is {agent_id}'s own tool group. To turn it "
                f"off, move that folder out of {_tilde(tools_dir)}."
            )
        raise AddonError(f"{name} isn't on for {agent_id}.")

    settings.replace(tools_dir / f"{name}{OFF}")
    print(f"{name} is off for {agent_id}. Its settings are kept, and come "
          f"back if you turn it on again.")
    group = available().get(name)
    if group and group.keys:
        print(f"Its keys are still stored; 'bountiful keys {agent_id} {name} "
              f"--delete' removes them.")
    print(f"It takes effect the next time {agent_id} starts.")


def keys(agent_id: str, name: str, delete: bool = False) -> None:
    """bountiful keys <agent> <group>: store, replace, or delete its keys."""
    group = _group(name)
    if not group.keys:
        print(f"{name} needs no keys.")
        return

    try:
        if delete:
            for k in group.keys:
                if delete_key(agent_id, name, k["name"]):
                    print(f"  {k['label']}: deleted")
            return

        if not sys.stdin.isatty():
            raise AddonError("Storing keys needs someone at the keyboard.")

        print(f"{name} keys for {agent_id}, kept in your system keyring.\n")
        for k in group.keys:
            stored = get_key(agent_id, name, k["name"])
            print(f"  {k['label']} [{'stored' if stored else 'not stored'}]")
            if stored:
                if input("    Replace it? [y/N] ").strip().lower() != "y":
                    continue
            value = _read_key(k)
            if not value:
                print("    skipped")
                continue
            set_key(agent_id, name, k["name"], value)
            print("    stored")
    except KeyringUnavailable as e:
        raise AddonError(str(e)) from e

    print("\nKeys are read each time a tool runs, so they work right away.")


def _read_key(key: dict) -> str:
    """Ask for one key: pasted out of sight, or read from a file.

    A key that spans lines, such as a private key in a .pem file, is
    read from its file, since a hidden prompt takes only one line.
    """
    if key.get("from_file"):
        answer = input("    The file's path (Enter to skip): ").strip()
        if not answer:
            return ""
        path = Path(answer.strip("'\"")).expanduser()
        try:
            return path.read_text().strip()
        except OSError as e:
            raise AddonError(f"Couldn't read {path}: {e.strerror}") from e
    return getpass.getpass("    Paste it (hidden; Enter to skip): ").strip()
