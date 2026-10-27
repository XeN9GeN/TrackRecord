from html.parser import HTMLParser

import pytest
from django.template import Context, Template

from core.markdown import ALLOWED_TAGS, render_markdown, render_markdown_plain


class TagCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, attrs))


class TestRenderMarkdown:
    def test_basic_formatting(self):
        html = render_markdown("**bold** and *italic* ~~old~~")
        assert "<strong>bold</strong>" in html
        assert "<em>italic</em>" in html
        assert "<s>old</s>" in html

    def test_single_line_breaks_are_kept(self):
        assert "<br>" in render_markdown("first\nsecond")

    def test_headings_are_demoted(self):
        html = render_markdown("# Top\n\n## Second\n\n### Third")
        assert "<h3>Top</h3>" in html
        assert "<h4>Second</h4>" in html
        assert "<h4>Third</h4>" in html
        assert "<h1" not in html and "<h2" not in html

    def test_tables(self):
        html = render_markdown("| a | b |\n|---|---|\n| 1 | 2 |")
        assert "<table>" in html
        assert "<td>2</td>" in html

    def test_links_get_rel(self):
        html = render_markdown("see https://example.com")
        assert 'href="https://example.com"' in html
        assert 'rel="noopener noreferrer"' in html

    @pytest.mark.parametrize(
        "source",
        [
            "<script>alert(1)</script>",
            '<img src=x onerror="alert(1)">',
            "[click](javascript:alert(1))",
            '<a href="javascript:alert(1)">x</a>',
            "<iframe src='https://evil'></iframe>",
            '<div onclick="alert(1)">x</div>',
        ],
    )
    def test_no_script_injection(self, source):
        parser = TagCollector()
        parser.feed(render_markdown(source))
        for tag, attrs in parser.tags:
            assert tag in ALLOWED_TAGS
            for name, value in attrs:
                assert not name.startswith("on")
                assert not (value or "").strip().lower().startswith("javascript:")

    def test_raw_html_is_shown_as_text(self):
        assert "&lt;b&gt;" in render_markdown("<b>x</b>")

    def test_images_are_not_rendered(self):
        html = render_markdown("![photo](https://example.com/a.png)")
        assert "<img" not in html

    def test_empty(self):
        assert render_markdown("") == ""
        assert render_markdown(None) == ""


class TestRenderMarkdownPlain:
    def test_strips_markup(self):
        assert render_markdown_plain("# Title\n\n- **one**\n- `two`\n\n[link](https://x.y)") == "Title one two link"

    def test_template_escapes_plain_text(self):
        rendered = Template("{% load markdown_tags %}{{ text|render_markdown_plain }}").render(
            Context({"text": "<script>x</script>"})
        )
        assert "<script>" not in rendered
        assert "&lt;script&gt;" in rendered


def test_filter_output_is_safe_html():
    rendered = Template("{% load markdown_tags %}{{ text|render_markdown }}").render(Context({"text": "**a**"}))
    assert "<strong>a</strong>" in rendered
