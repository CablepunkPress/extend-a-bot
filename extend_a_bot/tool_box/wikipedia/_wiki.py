"""Shared Wikipedia access: the API address, identification, and requests.

Wikimedia asks every program that calls its API to identify itself
with a User-Agent naming the program and a way to reach its makers,
and limits clients that don't. Requests are small and made one at a
time, at a person's pace, which is well within what it allows
anonymous clients.

Standard library only.
"""

import json
import re
import urllib.error
import urllib.parse
import urllib.request

from extend_a_bot import __version__

USER_AGENT = (
    f"Bountiful/{__version__} "
    "(https://github.com/CablepunkPress/extend-a-bot; a personal research agent)"
)
TIMEOUT = 20

_LANGUAGE = re.compile(r"^[a-z][a-z-]{1,15}$")


class WikipediaError(RuntimeError):
    """A failed request. The message is for the model to relay."""


def language(context: dict) -> str:
    """The agent's Wikipedia language code, checked, defaulting to en."""
    code = str(context["settings"].get("language", "en")).strip().lower()
    if not _LANGUAGE.match(code):
        raise WikipediaError(
            f"The Wikipedia language setting '{code}' isn't a language code "
            f"such as 'en'. The user can fix it in the agent's tools/wikipedia.toml."
        )
    return code


MAX_CHARACTERS = 4000


def max_characters(context: dict) -> int:
    value = context["settings"].get("max_characters", MAX_CHARACTERS)
    return value if isinstance(value, int) and value > 0 else MAX_CHARACTERS


def article_url(lang: str, title: str) -> str:
    return f"https://{lang}.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_"))


def query(lang: str, params: dict) -> dict:
    """Call the MediaWiki Action API and return its JSON."""
    params = {**params, "format": "json", "formatversion": "2"}
    url = f"https://{lang}.wikipedia.org/w/api.php?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise WikipediaError(
                "Wikipedia is limiting requests right now. Try again in a minute."
            ) from e
        raise WikipediaError(f"Wikipedia returned an error (HTTP {e.code}).") from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise WikipediaError(
            "Wikipedia couldn't be reached. This computer may be offline."
        ) from e
    if "error" in data:
        raise WikipediaError(f"Wikipedia said: {data['error'].get('info', 'error')}")
    return data


def strip_tags(text: str) -> str:
    """Remove the HTML tags Wikipedia puts around search matches."""
    return re.sub(r"<[^>]+>", "", text)
