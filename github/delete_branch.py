"""Tool: delete a branch from a GitHub repository."""

import json
import logging

import httpx

from _auth import GITHUB_API, GITHUB_OWNER, auth_headers

logger = logging.getLogger(__name__)

TOOL = {
    "name": "delete_branch",
    "description": (
        f"Delete a branch from a {GITHUB_OWNER} repository. "
        f"Refuses to delete the repo's default branch."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "repo": {
                "type": "string",
                "description": "Repository name",
            },
            "branch": {
                "type": "string",
                "description": "Branch name to delete",
            },
        },
        "required": ["repo", "branch"],
    },
}


def handler(context, repo, branch):
    """Delete a branch from a GitHub repository."""
    h = auth_headers()

    # Guard: refuse to delete the default branch
    repo_resp = httpx.get(f"{GITHUB_API}/repos/{GITHUB_OWNER}/{repo}", headers=h)
    repo_resp.raise_for_status()
    default_branch = repo_resp.json()["default_branch"]

    if branch == default_branch:
        return json.dumps({"error": f"Cannot delete the default branch '{branch}'"})

    resp = httpx.delete(
        f"{GITHUB_API}/repos/{GITHUB_OWNER}/{repo}/git/refs/heads/{branch}",
        headers=h,
    )

    if resp.status_code == 422:
        return json.dumps({"error": f"Branch not found: {branch}"})

    resp.raise_for_status()

    logger.info("Deleted branch %s/%s:%s", GITHUB_OWNER, repo, branch)

    return json.dumps({
        "status": "deleted",
        "branch": branch,
        "repo": f"{GITHUB_OWNER}/{repo}",
    })
