"""Study pages: Markdown rendered with raw HTML disabled (safe mode)."""

import re

from markdown_it import MarkdownIt
from markupsafe import Markup

__all__ = ["render_markdown"]

_MD = MarkdownIt("commonmark", {"html": False, "linkify": False, "typographer": False}).enable(
    "table"
)

_MARKER_LINE = re.compile(r"^<!-- [A-Z][A-Z0-9_]* -->[ \t]*(?:\r?\n|$)", re.MULTILINE)
"""A generated-block marker such as ``<!-- ERRATA_TABLE_START -->`` alone on its line."""


def render_markdown(text: str) -> Markup:
    """HTML for ``text``. Raw HTML in the source is escaped, and markdown-it's link validation
    drops ``javascript:``/``vbscript:``/``data:`` URLs, so the result is safe to embed.

    Lines holding only a generated-block marker (``gerald_na.registry.generated``) are dropped
    first: with raw HTML disabled they would otherwise appear as literal text."""
    return Markup(_MD.render(_MARKER_LINE.sub("", text)))  # noqa: S704 - html disabled: escaped
