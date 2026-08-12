"""Tool: read a file from a GitHub repository."""

import base64
import json
import logging

import httpx

from _auth import GITHUB_API, GITHUB_OWNER, auth_headers

logger = logging.getLogger(__name__)

TOOL = {
    "name": "read_file",
    "description": f"Read the contents of a file in a {GITHUB_OWNER} repository.",
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
        },
        "required": ["repo", "path"],
    },
}


def handler(context, repo, path):
    """Read the contents of a file in a GitHub repository."""
    logger.info("Reading file %s/%s/%s", GITHUB_OWNER, repo, path)
    url = f"{GITHUB_API}/repos/{GITHUB_OWNER}/{repo}/contents/{path}"
    resp = httpx.get(url, headers=auth_headers())
    resp.raise_for_status()

    data = resp.json()

    if data.get("type") != "file":
        return json.dumps({"error": f"'{path}' is not a file, it is a {data.get('type')}"})

    content = base64.b64decode(data["content"]).decode()

    return json.dumps({
        "path": data["path"],
        "size": data["size"],
        "sha": data["sha"],
        "content": content,
    })
