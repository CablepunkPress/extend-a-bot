"""Tool: merge a pull request in a GitHub repository."""

import json
import logging

import httpx

from _auth import GITHUB_API, GITHUB_OWNER, auth_headers

logger = logging.getLogger(__name__)

TOOL = {
    "name": "merge_pull_request",
    "description": (
        f"Merge an open pull request in a {GITHUB_OWNER} repository. "
        f"Uses merge commit (not squash or rebase) to preserve commit history."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "repo": {
                "type": "string",
                "description": "Repository name",
            },
            "pull_number": {
                "type": "integer",
                "description": "Pull request number",
            },
            "commit_title": {
                "type": "string",
                "description": "Optional: custom merge commit title. Defaults to GitHub's standard merge message.",
            },
        },
        "required": ["repo", "pull_number"],
    },
}


def handler(context, repo, pull_number, commit_title=None):
    """Merge a pull request."""
    h = auth_headers()

    # Check PR state before attempting merge
    pr_resp = httpx.get(
        f"{GITHUB_API}/repos/{GITHUB_OWNER}/{repo}/pulls/{pull_number}",
        headers=h,
    )
    pr_resp.raise_for_status()
    pr_data = pr_resp.json()

    if pr_data.get("merged"):
        return json.dumps({
            "error": f"PR #{pull_number} is already merged",
            "merged_at": pr_data.get("merged_at"),
            "repo": f"{GITHUB_OWNER}/{repo}",
        })

    if pr_data.get("state") != "open":
        return json.dumps({
            "error": f"PR #{pull_number} is {pr_data.get('state')}, not open",
            "repo": f"{GITHUB_OWNER}/{repo}",
        })

    payload = {"merge_method": "merge"}
    if commit_title:
        payload["commit_title"] = commit_title

    resp = httpx.put(
        f"{GITHUB_API}/repos/{GITHUB_OWNER}/{repo}/pulls/{pull_number}/merge",
        headers=h,
        json=payload,
    )
    resp.raise_for_status()

    data = resp.json()
    logger.info("Merged PR #%d on %s/%s (sha: %s)", pull_number, GITHUB_OWNER, repo, data["sha"][:7])

    return json.dumps({
        "status": "merged",
        "sha": data["sha"][:7],
        "message": data.get("message", "Pull request merged"),
        "repo": f"{GITHUB_OWNER}/{repo}",
        "pull_number": pull_number,
    })
