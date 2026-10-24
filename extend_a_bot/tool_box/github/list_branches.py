"""Tool: list branches in a GitHub repository."""

import json
import logging

import httpx

from _auth import GITHUB_API, auth_headers, normalize_repo, owner

logger = logging.getLogger(__name__)

TOOL = {
    "name": "list_branches",
    "description": "List branches in a {{ owner }} repository.",
    "input_schema": {
        "type": "object",
        "properties": {
            "repo": {
                "type": "string",
                "description": "Repository name",
            },
        },
        "required": ["repo"],
    },
}


def handler(context, repo):
    """List branches in a GitHub repository."""
    account = owner(context)
    repo = normalize_repo(repo)
    h = auth_headers(context)

    # Get the default branch name
    repo_resp = httpx.get(f"{GITHUB_API}/repos/{account}/{repo}", headers=h)
    repo_resp.raise_for_status()
    default_branch = repo_resp.json()["default_branch"]

    # List all branches
    resp = httpx.get(
        f"{GITHUB_API}/repos/{account}/{repo}/branches",
        headers=h,
        params={"per_page": 100},
    )
    resp.raise_for_status()
    branches = resp.json()

    if not branches:
        return "No branches found."

    lines = []
    for b in branches:
        name = b["name"]
        sha = b["commit"]["sha"][:7]
        marker = " (default)" if name == default_branch else ""
        lines.append(f"- {name} [{sha}]{marker}")

    return f"{len(branches)} branch(es):\n" + "\n".join(lines)
