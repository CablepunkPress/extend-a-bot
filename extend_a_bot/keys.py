"""Each agent's keys, kept in the system keyring.

The keyring service is the agent's id, the same id as in its
agent.json, and each key is named by its group, as in
"brave.api_key". So every agent has its own keys, two agents never
share one by accident, and a key never sits in an agent's folder,
where it could be copied or committed along with it.

Tools read their keys at call time, through the agent_id in their
context, never when they're imported.
"""

import keyring
import keyring.errors


class KeyringUnavailable(RuntimeError):
    """The keyring couldn't be reached. The message is user-facing."""


def _name(group: str, key: str) -> str:
    return f"{group}.{key}"


def get_key(agent_id: str, group: str, key: str) -> str | None:
    """One of an agent's keys, or None if it isn't stored."""
    try:
        return keyring.get_password(agent_id, _name(group, key)) or None
    except keyring.errors.KeyringError as e:
        raise KeyringUnavailable(f"Couldn't read the system keyring: {e}") from e


def set_key(agent_id: str, group: str, key: str, value: str) -> None:
    """Store one of an agent's keys, and check it reads back."""
    try:
        keyring.set_password(agent_id, _name(group, key), value)
        stored = keyring.get_password(agent_id, _name(group, key))
    except keyring.errors.KeyringError as e:
        raise KeyringUnavailable(f"Couldn't write to the system keyring: {e}") from e
    if stored != value:
        raise KeyringUnavailable("The key was stored but couldn't be read back.")


def delete_key(agent_id: str, group: str, key: str) -> bool:
    """Remove one of an agent's keys. Returns False if it wasn't stored."""
    try:
        keyring.delete_password(agent_id, _name(group, key))
        return True
    except keyring.errors.PasswordDeleteError:
        return False
    except keyring.errors.KeyringError as e:
        raise KeyringUnavailable(f"Couldn't write to the system keyring: {e}") from e
