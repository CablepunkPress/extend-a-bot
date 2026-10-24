"""Tool: search Wikipedia for articles."""

import json
import logging

import _wiki

logger = logging.getLogger(__name__)

MAX_RESULTS = 10

TOOL = {
    "name": "search_wikipedia",
    "description": (
        "Search Wikipedia for articles about a subject. Use it to check a "
        "fact about the world before stating it, especially names, dates, "
        "numbers, and details of less familiar subjects, or when the user "
        "questions something you said. Returns article titles with a short "
        "matching excerpt; read an article with read_wikipedia. Wikipedia "
        "knows nothing about your conversations with the user; search your "
        "archive for those."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "What to search for, such as a name, title, or subject",
            },
            "limit": {
                "type": "integer",
                "description": f"How many articles to return, 1 to {MAX_RESULTS}. Default 5.",
            },
        },
        "required": ["query"],
    },
}


def handler(context, query="", limit=5):
    if not str(query).strip():
        return json.dumps({"error": "Give something to search for."})

    lang = _wiki.language(context)
    try:
        limit = max(1, min(int(limit), MAX_RESULTS))
    except (TypeError, ValueError):
        limit = 5
    logger.info("Searching %s.wikipedia.org", lang)

    data = _wiki.query(lang, {
        "action": "query",
        "list": "search",
        "srsearch": str(query),
        "srlimit": limit,
        "srprop": "snippet",
    })
    results = [
        {
            "title": hit["title"],
            "excerpt": _wiki.strip_tags(hit.get("snippet", "")),
            "url": _wiki.article_url(lang, hit["title"]),
        }
        for hit in data.get("query", {}).get("search", [])
    ]
    if not results:
        return json.dumps({"results": [], "note": "No Wikipedia article matched."})
    return json.dumps({"results": results})
