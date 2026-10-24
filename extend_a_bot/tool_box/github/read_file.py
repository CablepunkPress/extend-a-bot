"""Tool: read a file from a GitHub repository."""

import base64
import json
import logging

import httpx

from _auth import GITHUB_API, auth_headers, normalize_repo, owner

logger = logging.getLogger(__name__)

TOOL = {
    "name": "read_file",
    "description": "Read the contents of a file in a {{ owner }} repository.",
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
            "ref": {
                "type": "string",
                "description": "Optional: branch, tag, or commit SHA to read from. Defaults to the repo's default branch.",
            },
        },
        "required": ["repo", "path"],
    },
}


def handler(context, repo, path, ref=None):
    """Read the contents of a file in a GitHub repository."""
    repo = normalize_repo(repo)
    account = owner(context)
    logger.info("Reading file %s/%s/%s", account, repo, path)
    url = f"{GITHUB_API}/repos/{account}/{repo}/contents/{path}"

    params = {}
    if ref:
        params["ref"] = ref

    resp = httpx.get(url, headers=auth_headers(context), params=params)
    if resp.status_code == 404:
        return json.dumps({"error": f"File not found: {path}"})
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
