"""Search the web with Brave Search."""

import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request

from extend_a_bot.keys import KeyringUnavailable, get_key

logger = logging.getLogger(__name__)

ENDPOINT = "https://api.search.brave.com/res/v1/llm/context"
TIMEOUT = 30
SAFESEARCH = ("off", "moderate", "strict")

# The most text one search returns, in Brave's tokens (1,024 to
# 32,768). Each search's results stay in the conversation until the
# turn ends, costing time and memory.
MAX_TOKENS = 2048

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}")

NOTE = (
    "These pages come from Brave's index, not a live view of the web, so "
    "don't describe them as live or real-time: a page's date says when it "
    "was written. Prefer official and primary sources, such as a company's "
    "own site, a government page, or the original report, over pages that "
    "repeat them. When the sources disagree, say plainly which says what, "
    "rather than searching again to settle it."
)

TOOL = {
    "name": "search_web",
    "description": (
        "Search the web with Brave Search. Use it for recent events, news, "
        "and subjects too new or too small for Wikipedia. Returns passages "
        "from the pages found, each with its page's title, address, and date "
        "when known. Each search is paid for by the user, so search only when "
        "it will settle a question, and prefer search_wikipedia, if you have "
        "it, for well-documented subjects. One search usually answers a "
        "question; search again only for a different question, not to check "
        "the same one twice."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "What to search for, in a few words",
            },
        },
        "required": ["query"],
    },
}


def _max_tokens(settings: dict) -> int:
    value = settings.get("max_tokens", MAX_TOKENS)
    if not isinstance(value, int):
        return MAX_TOKENS
    return max(1024, min(value, 32768))


def _date(age) -> str:
    """The page's date as YYYY-MM-DD, from Brave's list of renderings."""
    for item in age or []:
        if isinstance(item, str) and _DATE.match(item):
            return item[:10]
    return ""


def _site(url: str) -> str:
    """A page's site: "https://www.example.com/a" becomes "example.com"."""
    host = urllib.parse.urlparse(url).hostname or ""
    return host[4:] if host.startswith("www.") else host


def _cite(results: list[dict]) -> str:
    """Ends a result, so it's the last thing the model reads before answering."""
    site = next((_site(r["url"]) for r in results if _site(r["url"])), "example.com")
    return (
        "When you answer from these, name the sites your answer comes from "
        f'in your reply itself, for example: "According to {site}, …"'
    )


def handler(context, query=""):
    query = str(query).strip()
    if not query:
        return json.dumps({"error": "Give something to search for."})

    try:
        key = get_key(context["agent_id"], "brave", "api_key")
    except KeyringUnavailable as e:
        return json.dumps({"error": str(e)})
    if not key:
        return json.dumps({"error": "This agent has no Brave Search API key stored."})

    settings = context["settings"]
    params = {"q": query, "maximum_number_of_tokens": _max_tokens(settings)}
    if settings.get("country"):
        params["country"] = str(settings["country"]).lower()
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
            message = "Brave refused this agent's API key."
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
    except ValueError:
        return json.dumps({"error": "Brave Search sent a reply that couldn't be read."})

    sources = data.get("sources") or {}
    results = []
    for hit in (data.get("grounding") or {}).get("generic") or []:
        url = hit.get("url", "")
        source = sources.get(url) or {}
        result = {
            "title": hit.get("title") or source.get("title", ""),
            "url": url,
            "passages": [s for s in hit.get("snippets") or [] if isinstance(s, str)],
        }
        date = _date(source.get("age"))
        if date:
            result["date"] = date
        results.append(result)

    if not results:
        return json.dumps({"results": [], "note": "The search found nothing relevant."})
    return json.dumps({
        "results": results,
        "sources": [{"title": r["title"], "url": r["url"]} for r in results],
        "note": NOTE,
        "cite": _cite(results),
    })
