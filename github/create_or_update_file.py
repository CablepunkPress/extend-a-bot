"""Tool: create or update a file in a GitHub repository."""

import base64
import json
import logging
import re

import httpx

from _auth import GITHUB_API, GITHUB_OWNER, GITHUB_COMMITTER_NAME, GITHUB_COMMITTER_EMAIL, GITHUB_COAUTHOR, auth_headers

logger = logging.getLogger(__name__)

TOOL = {
    "name": "create_or_update_file",
    "description": (
        f"Create or update a file in a {GITHUB_OWNER} repository. "
        f"Commits to the specified branch, or the repo's default branch if none given."
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
                "description": "File path within the repository (e.g., 'README.md')",
            },
            "content": {
                "type": "string",
                "description": "The full content of the file",
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
        "required": ["repo", "path", "content", "message"],
    },
}


def handler(context, repo, path, content, message, branch=None):
    """Create or update a file in a GitHub repository."""
    logger.info("Creating/updating %s/%s/%s", GITHUB_OWNER, repo, path)
    url = f"{GITHUB_API}/repos/{GITHUB_OWNER}/{repo}/contents/{path}"
    h = auth_headers()

    # Strip any co-author trailers the model may have added
    message = re.sub(r'\n*Co-authored-by:.*', '', message, flags=re.IGNORECASE).strip()

    # Append co-author trailer if configured
    if GITHUB_COAUTHOR:
        message = f"{message}\n\nCo-authored-by: {GITHUB_COAUTHOR}"

    params = {}
    if branch:
        params["ref"] = branch

    sha = None
    existing = httpx.get(url, headers=h, params=params)
    if existing.status_code == 200:
        sha = existing.json()["sha"]
        logger.info("File exists, updating (sha=%s)", sha[:7])

    committer = {
        "name": GITHUB_COMMITTER_NAME,
        "email": GITHUB_COMMITTER_EMAIL,
    }

    payload = {
        "message": message,
        "content": base64.b64encode(content.encode()).decode(),
        "committer": committer,
        "author": committer,
    }
    if sha:
        payload["sha"] = sha
    if branch:
        payload["branch"] = branch

    resp = httpx.put(url, headers=h, json=payload)
    resp.raise_for_status()

    result = resp.json()
    action = "updated" if sha else "created"
    return json.dumps({
        "status": action,
        "path": result["content"]["path"],
        "sha": result["content"]["sha"],
        "html_url": result["content"]["html_url"],
    })
