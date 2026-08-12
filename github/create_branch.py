"""Tool: create a branch in a GitHub repository."""

import json
import logging

import httpx

from _auth import GITHUB_API, GITHUB_OWNER, auth_headers

logger = logging.getLogger(__name__)

TOOL = {
    "name": "create_branch",
    "description": (
        f"Create a new branch in a {GITHUB_OWNER} repository. "
        f"Branches from the repo's default branch unless a source ref is specified."
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
                "description": "Name for the new branch (e.g., 'add-readme', 'cablepunk/update-config')",
            },
            "from_ref": {
                "type": "string",
                "description": "Optional: source branch or SHA to branch from. Defaults to the repo's default branch.",
            },
        },
        "required": ["repo", "branch"],
    },
}


def handler(context, repo, branch, from_ref=None):
    """Create a new branch in a GitHub repository."""
    h = auth_headers()

    # Resolve the source SHA
    if not from_ref:
        # Get the repo's default branch
        repo_resp = httpx.get(f"{GITHUB_API}/repos/{GITHUB_OWNER}/{repo}", headers=h)
        repo_resp.raise_for_status()
        from_ref = repo_resp.json()["default_branch"]

    # Get the SHA of the source ref
    ref_resp = httpx.get(
        f"{GITHUB_API}/repos/{GITHUB_OWNER}/{repo}/git/ref/heads/{from_ref}",
        headers=h,
    )
    ref_resp.raise_for_status()
    source_sha = ref_resp.json()["object"]["sha"]

    # Create the new branch
    create_resp = httpx.post(
        f"{GITHUB_API}/repos/{GITHUB_OWNER}/{repo}/git/refs",
        headers=h,
        json={
            "ref": f"refs/heads/{branch}",
            "sha": source_sha,
        },
    )
    create_resp.raise_for_status()

    logger.info("Created branch %s/%s:%s from %s", GITHUB_OWNER, repo, branch, source_sha[:7])

    return json.dumps({
        "status": "created",
        "branch": branch,
        "from_sha": source_sha[:7],
        "repo": f"{GITHUB_OWNER}/{repo}",
    })
