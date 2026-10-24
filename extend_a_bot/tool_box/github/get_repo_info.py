"""Tool: get metadata about a GitHub repository."""

import logging

import httpx

from _auth import GITHUB_API, auth_headers, normalize_repo, owner

logger = logging.getLogger(__name__)

TOOL = {
    "name": "get_repo_info",
    "description": (
        "Get metadata about a {{ owner }} repository: description, "
        "default branch, visibility, last push time, open issues count."
    ),
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
    """Get metadata about a repository."""
    account = owner(context)
    repo = normalize_repo(repo)
    resp = httpx.get(
        f"{GITHUB_API}/repos/{account}/{repo}",
        headers=auth_headers(context),
    )
    resp.raise_for_status()
    data = resp.json()

    fields = {
        "full_name": data["full_name"],
        "description": data.get("description") or "(no description)",
        "private": data["private"],
        "default_branch": data["default_branch"],
        "open_issues": data["open_issues_count"],
        "pushed_at": data["pushed_at"],
        "html_url": data["html_url"],
    }
    return "\n".join(f"{k}: {v}" for k, v in fields.items())
