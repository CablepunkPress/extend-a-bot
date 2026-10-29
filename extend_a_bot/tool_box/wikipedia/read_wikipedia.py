"""Tool: read a Wikipedia article, or one of its sections, as plain text.

An article's opening comes from Wikipedia's plain-text extracts. A
section comes from the article's rendered page instead, because the
plain-text extracts leave out anything inside a <div> or a table,
which on Wikipedia includes most cast lists, discographies, and
rosters laid out in columns. Reading a section that way also brings
its subsections along, so "Cast" includes "Main cast".
"""

import html
import json
import logging
import re
from html.parser import HTMLParser

import _wiki

logger = logging.getLogger(__name__)

TOOL = {
    "name": "read_wikipedia",
    "description": (
        "Read a Wikipedia article as plain text, by its exact title from "
        "search_wikipedia. A long article returns its opening and a list of "
        "its sections; call again with a section name to read that part. "
        "A section includes its subsections, lists, and tables. "
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

# Parts of a rendered page that aren't part of its text: styles,
# images, footnote markers like [5], and the reference list.
_SKIP_TAGS = {"style", "script", "figure"}
_SKIP_CLASSES = {
    "reference", "mw-editsection", "noprint", "reflist",
    "mw-references-wrap", "navbox", "metadata",
}
# Elements that never have a closing tag.
_VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "source", "track", "wbr",
}
# Elements that start on a new line.
_BLOCK_TAGS = {"p", "div", "ul", "ol", "dl", "table", "blockquote"}
_HEADING_TAG = re.compile(r"^h([2-6])$")


class _PlainText(HTMLParser):
    """Turn a rendered Wikipedia section into plain text.

    Headings become "== Heading ==" lines, matching the extracts, list
    items become "- " lines, and table cells are joined with " | ".
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        # One entry per open element: its tag, and whether it or an
        # element around it is being skipped.
        self.stack = []
        self.cells = 0
        # How many table cells are open; a line break inside one would
        # split its row, so it becomes "; " instead.
        self.in_cell = 0

    def _skipping(self) -> bool:
        return bool(self.stack) and self.stack[-1][1]

    def handle_starttag(self, tag, attrs):
        if tag in _VOID_TAGS:
            if tag == "br" and not self._skipping():
                self.parts.append("; " if self.in_cell else "\n")
            return
        classes = set((dict(attrs).get("class") or "").split())
        skipping = (
            self._skipping() or tag in _SKIP_TAGS or bool(classes & _SKIP_CLASSES)
        )
        self.stack.append((tag, skipping))
        if skipping:
            return
        heading = _HEADING_TAG.match(tag)
        if heading:
            self.parts.append("\n\n" + "=" * int(heading.group(1)) + " ")
        elif tag == "li":
            self.parts.append("\n- ")
        elif tag == "tr":
            self.parts.append("\n")
            self.cells = 0
        elif tag in ("td", "th"):
            if self.cells:
                self.parts.append(" | ")
            self.cells += 1
            self.in_cell += 1
        elif tag in ("dt", "dd"):
            self.parts.append("\n")
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in _VOID_TAGS:
            return
        # Close the nearest open element with this tag, along with
        # anything left open inside it; ignore a stray closing tag.
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                skipping = self.stack[i][1]
                if not skipping:
                    self.in_cell -= sum(
                        1 for t, skip in self.stack[i:]
                        if t in ("td", "th") and not skip
                    )
                del self.stack[i:]
                break
        else:
            return
        if skipping:
            return
        heading = _HEADING_TAG.match(tag)
        if heading:
            self.parts.append(" " + "=" * int(heading.group(1)) + "\n")
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skipping():
            self.parts.append(re.sub(r"\s+", " ", data))

    def text(self) -> str:
        lines = [
            re.sub(r" {2,}", " ", line).strip()
            for line in "".join(self.parts).split("\n")
        ]
        return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _sections(text: str) -> list[tuple[str, str]]:
    """Split an extract into (heading, text) pairs; the opening has heading ""."""
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


def _find_section(lang: str, title: str, wanted: str):
    """Look a section up by heading.

    Returns ((heading, index), headings) when found, or (None, headings).
    The index is the section's number on the rendered page.
    """
    data = _wiki.query(lang, {"action": "parse", "page": title, "prop": "sections"})
    headings, found = [], None
    for entry in data.get("parse", {}).get("sections", []):
        index = str(entry.get("index", ""))
        if not index.isdigit():
            continue  # a section pulled in from another page
        heading = html.unescape(_wiki.strip_tags(entry.get("line", ""))).strip()
        headings.append(heading)
        if found is None and heading.lower() == wanted:
            found = (heading, index)
    return found, headings


def _section_text(lang: str, title: str, index: str) -> str:
    """One section of the rendered page, with its subsections, as plain text."""
    data = _wiki.query(lang, {
        "action": "parse",
        "page": title,
        "prop": "text",
        "section": index,
        "disableeditsection": "1",
        "disablelimitreport": "1",
    })
    parser = _PlainText()
    parser.feed(data.get("parse", {}).get("text", ""))
    parser.close()
    return parser.text()


def handler(context, title="", section=None):
    if not str(title).strip():
        return json.dumps({"error": "Give the title of an article to read."})

    lang = _wiki.language(context)
    limit = _wiki.max_characters(context)
    logger.info("Reading an article from %s.wikipedia.org", lang)

    # The extract finds the article, following redirects, and gives
    # its opening and its list of sections.
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
        found, page_headings = _find_section(lang, found_title, wanted)
        if not found:
            result["error"] = f"No section named '{section}'."
            result["sections"] = page_headings or headings
            return json.dumps(result)
        heading, index = found
        text = _section_text(lang, found_title, index)
        result["section"] = heading
        if not _HEADING.sub("", text).strip():
            result["text"] = ""
            result["note"] = "This section has no text on Wikipedia."
            return json.dumps(result)
        result["text"], cut = _cut(text, limit)
        if cut:
            # Drop a heading left at the end with nothing under it, so
            # it doesn't read as an empty section.
            result["text"] = re.sub(r"\n*^=.*=\s*\Z", "", result["text"], flags=re.MULTILINE)
            result["note"] = (
                "This section was cut short for length. Its subsections "
                "can each be read by calling read_wikipedia with their name."
            )
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
