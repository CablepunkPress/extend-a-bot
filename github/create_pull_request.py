"""Tool: create a pull request in a GitHub repository."""

import json
import logging

import httpx

from _auth import GITHUB_API, GITHUB_OWNER, auth_headers

logger = logging.getLogger(__name__)

TOOL = {
    "name": "create_pull_request",
    "description": (
        f"Create a pull request in a {GITHUB_OWNER} repository. "
        f"Merges from a source branch into the repo's default branch unless a target is specified."
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
                "description": "Source branch to merge from",
            },
            "title": {
                "type": "string",
                "description": "Pull request title",
            },
            "body": {
                "type": "string",
                "description": "Optional: pull request description",
            },
            "base": {
                "type": "string",
                "description": "Optional: target branch to merge into. Defaults to the repo's default branch.",
            },
        },
        "required": ["repo", "branch", "title"],
    },
}


def handler(context, repo, branch, title, body=None, base=None):
    """Create a pull request in a GitHub repository."""
    h = auth_headers()

    # Resolve the base branch if not specified
    if not base:
        repo_resp = httpx.get(f"{GITHUB_API}/repos/{GITHUB_OWNER}/{repo}", headers=h)
        repo_resp.raise_for_status()
        base = repo_resp.json()["default_branch"]

    payload = {
        "title": title,
        "head": branch,
        "base": base,
    }
    if body:
        payload["body"] = body

    resp = httpx.post(
        f"{GITHUB_API}/repos/{GITHUB_OWNER}/{repo}/pulls",
        headers=h,
        json=payload,
    )
    resp.raise_for_status()

    pr = resp.json()
    logger.info("Created PR #%d on %s/%s: %s → %s", pr["number"], GITHUB_OWNER, repo, branch, base)

    return json.dumps({
        "status": "created",
        "number": pr["number"],
        "title": pr["title"],
        "url": pr["html_url"],
        "head": branch,
        "base": base,
    })
