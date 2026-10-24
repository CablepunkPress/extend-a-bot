"""Shared GitHub App authentication and utilities.

Every value comes from the tool's context at call time: the agent's
keys from the keyring, under context["agent_id"], and its settings from
context["settings"], its tools/github.toml. So one copy of this code
serves every agent, each with its own GitHub App and account.
"""

import logging
import time

import httpx
import jwt

from extend_a_bot.keys import get_key

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
GROUP = "github"

# Installation tokens, per agent: agent_id → {"token", "expires_at"}
_token_cache: dict[str, dict] = {}


class GitHubSetupError(RuntimeError):
    """A key or setting is missing. The message is for the model to relay."""


def _key(context: dict, name: str) -> str:
    value = get_key(context["agent_id"], GROUP, name)
    if not value:
        raise GitHubSetupError(
            f"This agent has no GitHub {name.replace('_', ' ')} stored. "
            f"The user can add it with: bountiful keys {context['agent_id']} github"
        )
    return value


def setting(context: dict, name: str) -> str:
    """One of the agent's GitHub settings, required to be filled in."""
    value = context["settings"].get(name, "")
    if not value:
        raise GitHubSetupError(
            f"This agent's GitHub setting '{name}' is empty. The user can "
            f"fill it in, in the agent's tools/github.toml."
        )
    return value


def owner(context: dict) -> str:
    """The account or organization the agent works in."""
    return setting(context, "owner")


def _generate_jwt(context: dict) -> str:
    """Generate a JWT for GitHub App authentication."""
    now = int(time.time())
    payload = {
        "iat": now - 60,
        "exp": now + (10 * 60),
        "iss": _key(context, "app_id"),
    }
    return jwt.encode(payload, _key(context, "private_key"), algorithm="RS256")


def _get_installation_token(context: dict) -> str:
    """Exchange a JWT for an installation access token, cached per agent.

    Installation tokens are valid for one hour. Refreshes five minutes
    early to avoid edge-case expiry during a request.
    """
    agent_id = context["agent_id"]
    now = time.time()
    cached = _token_cache.get(agent_id)
    if cached and now < cached["expires_at"] - 300:
        return cached["token"]

    token = _generate_jwt(context)
    installation_id = _key(context, "installation_id")
    resp = httpx.post(
        f"{GITHUB_API}/app/installations/{installation_id}/access_tokens",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        },
    )
    resp.raise_for_status()

    data = resp.json()
    _token_cache[agent_id] = {
        "token": data["token"],
        "expires_at": now + (55 * 60),
    }
    logger.info("GitHub installation token refreshed")
    return data["token"]


def auth_headers(context: dict) -> dict:
    """Authenticated headers for GitHub API calls."""
    token = _get_installation_token(context)
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }


def committer(context: dict) -> dict:
    """The commit author and committer, from the agent's settings."""
    return {
        "name": setting(context, "committer_name"),
        "email": setting(context, "committer_email"),
    }


def with_coauthor(context: dict, message: str) -> str:
    """A commit message with the Co-authored-by line, if one is set."""
    coauthor = context["settings"].get("coauthor", "")
    if not coauthor:
        return message
    return f"{message}\n\nCo-authored-by: {coauthor}"


def normalize_repo(repo: str) -> str:
    """Strip owner prefix if the model passed 'owner/repo' instead of 'repo'."""
    return repo.split("/")[-1] if "/" in repo else repo
