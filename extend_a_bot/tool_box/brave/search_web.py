"""Tool: search the web with Brave Search.

The agent's key is read from the keyring at call time, under its id.
Standard library only.
"""

import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request

from extend_a_bot.keys import get_key

logger = logging.getLogger(__name__)

ENDPOINT = "https://api.search.brave.com/res/v1/web/search"
TIMEOUT = 20
MAX_RESULTS = 10
SAFESEARCH = ("off", "moderate", "strict")

TOOL = {
    "name": "search_web",
    "description": (
        "Search the web with Brave Search. Use it for recent events, news, "
        "and subjects too new or too small for Wikipedia. Each search is "
        "paid for by the user, so search only when it will settle a "
        "question, and prefer search_wikipedia, if you have it, for "
        "well-documented subjects. Returns pages with short excerpts; "
        "say which sites your answer comes from."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "What to search for",
            },
            "count": {
                "type": "integer",
                "description": f"How many results to return, 1 to {MAX_RESULTS}. Default 5.",
            },
        },
        "required": ["query"],
    },
}


def _clean(text: str) -> str:
    """Remove the HTML tags Brave puts around matches."""
    return re.sub(r"<[^>]+>", "", text or "")


def handler(context, query="", count=5):
    if not str(query).strip():
        return json.dumps({"error": "Give something to search for."})

    agent_id = context["agent_id"]
    key = get_key(agent_id, "brave", "api_key")
    if not key:
        return json.dumps({
            "error": "This agent has no Brave Search API key stored. The user "
                     f"can add one with: bountiful keys {agent_id} brave",
        })

    settings = context["settings"]
    try:
        count = max(1, min(int(count), MAX_RESULTS))
    except (TypeError, ValueError):
        count = 5
    params = {"q": str(query), "count": count, "extra_snippets": "true"}
    if settings.get("country"):
        params["country"] = str(settings["country"]).upper()
    if settings.get("search_lang"):
        params["search_lang"] = str(settings["search_lang"]).lower()
    if settings.get("safesearch") in SAFESEARCH:
        params["safesearch"] = settings["safesearch"]

    request = urllib.request.Request(
        ENDPOINT + "?" + urllib.parse.urlencode(params),
        headers={"Accept": "application/json", "X-Subscription-Token": key},
    )
    logger.info("Searching the web with Brave")
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            message = ("Brave refused this agent's API key. The user can check "
                       f"it, or store a new one with: bountiful keys {agent_id} brave")
        elif e.code == 429:
            message = ("Brave is limiting searches right now, or the plan's "
                       "credit is used up. Try again later.")
        else:
            message = f"Brave Search returned an error (HTTP {e.code})."
        return json.dumps({"error": message})
    except (urllib.error.URLError, TimeoutError):
        return json.dumps({
            "error": "Brave Search couldn't be reached. This computer may be offline.",
        })

    results = [
        {
            "title": _clean(hit.get("title", "")),
            "url": hit.get("url", ""),
            "excerpt": _clean(hit.get("description", "")),
            "more": [_clean(s) for s in hit.get("extra_snippets", [])][:3],
        }
        for hit in (data.get("web") or {}).get("results", [])[:count]
    ]
    if not results:
        return json.dumps({"results": [], "note": "The search found nothing."})
    return json.dumps({"results": results})
