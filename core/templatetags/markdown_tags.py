from django import template

from core import markdown

register = template.Library()


@register.filter
def render_markdown(text):
    return markdown.render_markdown(text)


@register.filter
def render_markdown_plain(text):
    return markdown.render_markdown_plain(text)
