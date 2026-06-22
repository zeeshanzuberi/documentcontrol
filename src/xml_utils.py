from __future__ import annotations

from typing import Any

from docx.oxml.ns import nsmap


def xml_xpath(element: Any, expression: str) -> list[Any]:
    """Run XPath on python-docx or raw lxml elements with Word namespaces bound."""

    try:
        return element.xpath(expression, namespaces=nsmap)
    except TypeError:
        return element.xpath(expression)
