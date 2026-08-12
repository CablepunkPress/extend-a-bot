"""Tool: list repositories accessible to the Cablepunk GitHub App."""

import logging

import httpx

from _auth import GITHUB_API, GITHUB_OWNER, auth_headers

logger = logging.getLogger(__name__)

TOOL = {
    "name": "list_repos",
    "description": (
        f"List all repositories the Cablepunk GitHub App can access "
        f"under the {GITHUB_OWNER} organization. "
        f"Use this to discover what repos are available before calling other GitHub tools."
    ),
    "input_schema": {
        "type": "object",
        "properties": {},
    },
}


def handler(context, **_):
    """List repositories accessible to the installation."""
    resp = httpx.get(
        f"{GITHUB_API}/installation/repositories",
        headers=auth_headers(),
        params={"per_page": 100},
    )
    resp.raise_for_status()
    data = resp.json()

    repos = [
        {
            "full_name": r["full_name"],
            "repo": r["name"],
            "private": r["private"],
            "default_branch": r["default_branch"],
        }
        for r in data.get("repositories", [])
    ]

    if not repos:
        return "No repositories are accessible."

    lines = [f"- {r['full_name']} (default branch: {r['default_branch']})" for r in repos]
    return f"{len(repos)} repositories accessible:\n" + "\n".join(lines)
