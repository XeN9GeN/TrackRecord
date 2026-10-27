"""The single rendering path for user-written Markdown (ADR-0008).

This is the only module allowed to call mark_safe on user content.
"""

import nh3
from django.utils.safestring import mark_safe
from markdown_it import MarkdownIt

ALLOWED_TAGS = {
    "p", "br", "strong", "em", "s", "del", "code", "pre", "blockquote",
    "ul", "ol", "li", "a", "h3", "h4", "hr",
    "table", "thead", "tbody", "tr", "th", "td",
}  # fmt: skip
ALLOWED_ATTRIBUTES = {"a": {"href", "title"}, "ol": {"start"}, "th": {"style"}, "td": {"style"}}
ALLOWED_URL_SCHEMES = {"http", "https", "mailto"}

_md = (
    MarkdownIt("commonmark", {"html": False, "breaks": True, "linkify": True})
    .enable(["table", "strikethrough", "linkify"])
    .disable("image")
)


def _demote_heading(self, tokens, idx, options, env):
    # Entry headings live inside the machine page: # becomes h3, everything deeper h4.
    token = tokens[idx]
    token.tag = "h3" if token.tag == "h1" else "h4"
    return self.renderToken(tokens, idx, options, env)


_md.add_render_rule("heading_open", _demote_heading)
_md.add_render_rule("heading_close", _demote_heading)


def render_markdown(text):
    """Markdown to sanitised HTML, safe to insert into a template."""
    html = _md.render(text or "")
    clean = nh3.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes=ALLOWED_URL_SCHEMES,
        link_rel="noopener noreferrer",
        filter_style_properties={"text-align"},
    )
    return mark_safe(clean)


def render_markdown_plain(text):
    """Text without markup for lists and previews; the template escapes it as usual."""
    parts = []
    for token in _md.parse(text or ""):
        if token.type != "inline":
            continue
        for child in token.children or []:
            if child.type in ("text", "code_inline"):
                parts.append(child.content)
            elif child.type in ("softbreak", "hardbreak"):
                parts.append(" ")
        parts.append(" ")
    return " ".join("".join(parts).split())
