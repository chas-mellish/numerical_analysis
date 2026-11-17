"""Study pages: Markdown rendered with raw HTML disabled (safe mode)."""

from markdown_it import MarkdownIt
from markupsafe import Markup

__all__ = ["render_markdown"]

_MD = MarkdownIt("commonmark", {"html": False, "linkify": False, "typographer": False}).enable(
    "table"
)


def render_markdown(text: str) -> Markup:
    """HTML for ``text``. Raw HTML in the source is escaped, and markdown-it's link validation
    drops ``javascript:``/``vbscript:``/``data:`` URLs, so the result is safe to embed."""
    return Markup(_MD.render(text))  # noqa: S704 - html disabled: the renderer escapes all input
