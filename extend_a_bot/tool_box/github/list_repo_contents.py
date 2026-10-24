"""Tool: list files and directories in a GitHub repository."""

import json
import logging

import httpx

from _auth import GITHUB_API, auth_headers, normalize_repo, owner

logger = logging.getLogger(__name__)

TOOL = {
    "name": "list_repo_contents",
    "description": (
        "List files and directories at a path in a {{ owner }} repository. "
        "Returns one level only. When results include directories (type='dir'), "
        "call this tool again with each directory path to explore its contents. "
        "Never assume a directory is empty without checking."
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
                "description": "Path within the repository. Empty string for root. To explore subdirectories, call this tool again for each 'dir' entry returned.",
                "default": "",
            },
        },
        "required": ["repo"],
    },
}


def handler(context, repo, path=""):
    """List files and directories at a path in a GitHub repository."""
    account = owner(context)
    repo = normalize_repo(repo)
    logger.info("Listing contents of %s/%s/%s", account, repo, path or "(root)")
    url = f"{GITHUB_API}/repos/{account}/{repo}/contents/{path}"
    resp = httpx.get(url, headers=auth_headers(context))
    resp.raise_for_status()

    data = resp.json()

    if isinstance(data, dict):
        return json.dumps({
            "type": "file",
            "items": [{"name": data["name"], "path": data["path"],
                        "type": data["type"], "size": data.get("size", 0)}],
        })

    return json.dumps({
        "type": "directory",
        "items": [
            {"name": item["name"], "path": item["path"],
             "type": item["type"], "size": item.get("size", 0)}
            for item in data
        ],
    })
