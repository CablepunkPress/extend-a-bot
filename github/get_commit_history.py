"""Tool: get recent commit history for a GitHub repository."""

import logging

import httpx

from _auth import GITHUB_API, GITHUB_OWNER, auth_headers

logger = logging.getLogger(__name__)

TOOL = {
    "name": "get_commit_history",
    "description": (
        f"Get recent commit history for a {GITHUB_OWNER} repository, "
        f"optionally filtered to a path or branch."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "repo": {
                "type": "string",
                "description": "Repository name",
            },
            "path": {
                "type": "string",
                "description": "Optional: only commits touching this file or directory path",
            },
            "branch": {
                "type": "string",
                "description": "Optional: branch or ref to query. Defaults to the repo's default branch.",
            },
            "limit": {
                "type": "integer",
                "description": "Max number of commits to return (default 10, max 30)",
                "default": 10,
            },
        },
        "required": ["repo"],
    },
}


def handler(context, repo, path=None, branch=None, limit=10):
    """Get recent commit history for a repository."""
    limit = min(max(int(limit), 1), 30)
    params = {"per_page": limit}
    if path:
        params["path"] = path
    if branch:
        params["sha"] = branch

    resp = httpx.get(
        f"{GITHUB_API}/repos/{GITHUB_OWNER}/{repo}/commits",
        headers=auth_headers(),
        params=params,
    )
    resp.raise_for_status()
    commits = resp.json()

    if not commits:
        return "No commits found for the given filters."

    lines = []
    for c in commits:
        sha = c["sha"][:7]
        author = c["commit"]["author"]["name"]
        date = c["commit"]["author"]["date"]
        message = c["commit"]["message"]
        subject = message.splitlines()[0]
        body = "\n".join(message.splitlines()[1:]).strip()

        entry = f"{sha} | {date} | {author} | {subject}"
        if body:
            entry += f"\n  {body}"
        lines.append(entry)

    return f"{len(commits)} commit(s):\n" + "\n".join(lines)
