"""Compare text and street addresses without losing house or suite numbers."""

import re
import html

WORDS = {
    "street": "st",
    "road": "rd",
    "avenue": "ave",
    "boulevard": "blvd",
    "drive": "dr",
    "lane": "ln",
    "pike": "pike",
    "pk": "pike",
    "north": "n",
    "south": "s",
    "east": "e",
    "west": "w",
    "northwest": "nw",
    "northeast": "ne",
    "southwest": "sw",
    "southeast": "se",
    "court": "ct",
}


def clean(text):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", " ", text))).strip()


def norm(text):
    return re.sub(r"[^a-z0-9]+", " ", str(text).lower()).strip()


def street(text):
    return " ".join(WORDS.get(word, word) for word in norm(text).split())
