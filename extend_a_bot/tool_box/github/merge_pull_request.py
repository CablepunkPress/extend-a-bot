"""Tool: merge a pull request in a GitHub repository.

Altered:    Merging is now reserved for human review.
            The delete branch tool for cleanup has also been removed.

The handler returns an error directing the assistant to inform the user 
they must handle it.

The tool stays in the catalog so the model understands the workflow:
PRs get merged.
"""

import json
import logging

from _auth import GITHUB_OWNER, normalize_repo

logger = logging.getLogger(__name__)

TOOL = {
    "name": "merge_pull_request",
    "description": (
        f"Merge an open pull request in a {GITHUB_OWNER} repository. "
        f"Merging is reserved for human review on GitHub."
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
        },
        "required": ["repo", "pull_number"],
    },
}


def handler(context, repo, pull_number, **_):
    """Merge is reserved for human review."""
    repo = normalize_repo(repo)
    return json.dumps({
        "error": "Pull requests must be reviewed and merged by a human on GitHub. "
        f"Review PR #{pull_number} at https://github.com/{GITHUB_OWNER}/{repo}/pull/{pull_number}",
    })
