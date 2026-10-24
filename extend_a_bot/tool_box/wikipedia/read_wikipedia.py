"""Tool: read a Wikipedia article, or one of its sections, as plain text."""

import json
import logging
import re

import _wiki

logger = logging.getLogger(__name__)

TOOL = {
    "name": "read_wikipedia",
    "description": (
        "Read a Wikipedia article as plain text, by its exact title from "
        "search_wikipedia. A long article returns its opening and a list of "
        "its sections; call again with a section name to read that part. "
        "Say that your answer comes from Wikipedia."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "The article's title, as search_wikipedia gave it",
            },
            "section": {
                "type": "string",
                "description": "Optional: a section heading, to read only that section",
            },
        },
        "required": ["title"],
    },
}

# A heading in plain-text extracts: "== Career ==", "=== Early life ==="
_HEADING = re.compile(r"^(={2,6})\s*(.+?)\s*\1\s*$", re.MULTILINE)


def _sections(text: str) -> list[tuple[str, str]]:
    """Split an article into (heading, text) pairs; the opening has heading ""."""
    parts = []
    last_heading, last_end = "", 0
    for match in _HEADING.finditer(text):
        parts.append((last_heading, text[last_end:match.start()].strip()))
        last_heading, last_end = match.group(2), match.end()
    parts.append((last_heading, text[last_end:].strip()))
    return [(h, t) for h, t in parts if h or t]


def _cut(text: str, limit: int) -> tuple[str, bool]:
    """Text up to limit characters, ending at a paragraph or sentence if it can."""
    if len(text) <= limit:
        return text, False
    cut = text[:limit]
    for mark in ("\n\n", ". "):
        at = cut.rfind(mark)
        if at > limit // 2:
            return cut[:at + 1].strip(), True
    return cut.strip(), True


def handler(context, title="", section=None):
    if not str(title).strip():
        return json.dumps({"error": "Give the title of an article to read."})

    lang = _wiki.language(context)
    limit = _wiki.max_characters(context)
    logger.info("Reading an article from %s.wikipedia.org", lang)

    data = _wiki.query(lang, {
        "action": "query",
        "prop": "extracts",
        "explaintext": "1",
        "exsectionformat": "wiki",
        "redirects": "1",
        "titles": str(title),
    })
    pages = data.get("query", {}).get("pages", [])
    if not pages or pages[0].get("missing") or "extract" not in pages[0]:
        return json.dumps({
            "error": f"No Wikipedia article is titled '{title}'. "
                     f"Search with search_wikipedia for the exact title.",
        })

    page = pages[0]
    found_title = page["title"]
    sections = _sections(page["extract"])
    headings = [h for h, _ in sections if h]
    result = {"title": found_title, "url": _wiki.article_url(lang, found_title)}

    if section:
        wanted = str(section).strip().lower()
        matches = [(h, t) for h, t in sections if h.lower() == wanted]
        if not matches:
            result["error"] = f"No section named '{section}'."
            result["sections"] = headings
            return json.dumps(result)
        heading, text = matches[0]
        result["section"] = heading
        result["text"], cut = _cut(text, limit)
        if cut:
            result["note"] = "This section was cut short for length."
        return json.dumps(result)

    whole = page["extract"].strip()
    if len(whole) <= limit:
        result["text"] = whole
        return json.dumps(result)

    opening = sections[0][1] if sections and not sections[0][0] else ""
    result["text"], _ = _cut(opening or whole, limit)
    result["sections"] = headings
    result["note"] = (
        "The article is long, so this is its opening. "
        "Read any section by calling read_wikipedia again with its name."
    )
    return json.dumps(result)
