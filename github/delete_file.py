"""Tool: delete a file from a GitHub repository."""

import json
import logging
import re

import httpx

from _auth import GITHUB_API, GITHUB_OWNER, GITHUB_COMMITTER_NAME, GITHUB_COMMITTER_EMAIL, GITHUB_COAUTHOR, auth_headers

logger = logging.getLogger(__name__)

TOOL = {
    "name": "delete_file",
    "description": (
        f"Delete a file from a {GITHUB_OWNER} repository. "
        f"Commits the deletion to the specified branch, or the repo's default branch if none given."
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
                "description": "File path within the repository (e.g., 'requirements.txt')",
            },
            "message": {
                "type": "string",
                "description": "Git commit message (subject line only — co-authorship is handled automatically)",
            },
            "branch": {
                "type": "string",
                "description": "Optional: branch to commit to. Defaults to the repo's default branch.",
            },
        },
        "required": ["repo", "path", "message"],
    },
}


def handler(context, repo, path, message, branch=None):
    """Delete a file from a GitHub repository."""
    logger.info("Deleting %s/%s/%s", GITHUB_OWNER, repo, path)
    url = f"{GITHUB_API}/repos/{GITHUB_OWNER}/{repo}/contents/{path}"
    h = auth_headers()

    # Strip any co-author trailers the model may have added
    message = re.sub(r'\n*Co-authored-by:.*', '', message, flags=re.IGNORECASE).strip()

    # Append co-author trailer if configured
    if GITHUB_COAUTHOR:
        message = f"{message}\n\nCo-authored-by: {GITHUB_COAUTHOR}"

    # Get the current file SHA (required by the API)
    params = {}
    if branch:
        params["ref"] = branch

    existing = httpx.get(url, headers=h, params=params)
    if existing.status_code == 404:
        return json.dumps({"error": f"File not found: {path}"})
    existing.raise_for_status()
    sha = existing.json()["sha"]

    committer = {
        "name": GITHUB_COMMITTER_NAME,
        "email": GITHUB_COMMITTER_EMAIL,
    }

    payload = {
        "message": message,
        "sha": sha,
        "committer": committer,
        "author": committer,
    }
    if branch:
        payload["branch"] = branch

    resp = httpx.request("DELETE", url, headers=h, json=payload)
    resp.raise_for_status()

    logger.info("Deleted %s/%s/%s", GITHUB_OWNER, repo, path)

    return json.dumps({
        "status": "deleted",
        "path": path,
        "repo": f"{GITHUB_OWNER}/{repo}",
    })
