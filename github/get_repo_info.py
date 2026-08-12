"""Tool: get metadata about a GitHub repository."""

import logging

import httpx

from _auth import GITHUB_API, GITHUB_OWNER, auth_headers

logger = logging.getLogger(__name__)

TOOL = {
    "name": "get_repo_info",
    "description": (
        f"Get metadata about a {GITHUB_OWNER} repository: description, "
        f"default branch, visibility, last push time, open issues count."
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
    resp = httpx.get(
        f"{GITHUB_API}/repos/{GITHUB_OWNER}/{repo}",
        headers=auth_headers(),
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
