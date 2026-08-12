"""Shared GitHub App authentication and configuration.

After installing this tool group, edit the values below for your
GitHub org and identity. Then run setup_keys.py to store your
GitHub App credentials in the system keyring.
"""

import logging
import time

import httpx
import jwt
import keyring

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Edit these for your setup
# ---------------------------------------------------------------------------

GITHUB_OWNER = ""               # your GitHub org or personal account
GITHUB_COMMITTER_NAME = ""      # git committer display name
GITHUB_COMMITTER_EMAIL = ""     # git committer email (noreply recommended)
GITHUB_COAUTHOR = ""            # Co-authored-by trailer, or "" to disable

# ---------------------------------------------------------------------------
# GitHub App credentials from system keyring (set via setup_keys.py)
# ---------------------------------------------------------------------------

GITHUB_API = "https://api.github.com"

KEYRING_SERVICE = "github-tools"
GITHUB_APP_ID = keyring.get_password(KEYRING_SERVICE, "github_app_id") or ""
GITHUB_APP_PRIVATE_KEY = keyring.get_password(KEYRING_SERVICE, "github_private_key") or ""
GITHUB_INSTALLATION_ID = keyring.get_password(KEYRING_SERVICE, "github_installation_id") or ""

_token_cache: dict = {"token": None, "expires_at": 0}


def _generate_jwt() -> str:
    """Generate a JWT for GitHub App authentication."""
    now = int(time.time())
    payload = {
        "iat": now - 60,
        "exp": now + (10 * 60),
        "iss": GITHUB_APP_ID,
    }
    return jwt.encode(payload, GITHUB_APP_PRIVATE_KEY, algorithm="RS256")


def _get_installation_token() -> str:
    """Exchange JWT for an installation access token, with caching.

    Installation tokens are valid for one hour. Refreshes five minutes
    early to avoid edge-case expiry during a request.
    """
    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires_at"] - 300:
        return _token_cache["token"]

    token = _generate_jwt()
    resp = httpx.post(
        f"{GITHUB_API}/app/installations/{GITHUB_INSTALLATION_ID}/access_tokens",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        },
    )
    resp.raise_for_status()

    data = resp.json()
    _token_cache["token"] = data["token"]
    _token_cache["expires_at"] = now + (55 * 60)

    logger.info("GitHub installation token refreshed")
    return data["token"]


def auth_headers() -> dict:
    """Get authenticated headers for GitHub API calls."""
    token = _get_installation_token()
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
