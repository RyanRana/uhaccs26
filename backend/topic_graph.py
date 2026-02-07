"""Utilities for topic graph node construction in SciScroll."""

import re


def slugify(text):
    """Convert text to a URL-safe slug."""
    if not text or not text.strip():
        return ""
    s = text.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"-{2,}", "-", s)
    s = s.strip("-")
    if len(s) > 80:
        s = s[:80].rsplit("-", 1)[0]
    return s


def make_node(label, description=""):
    """Create a node dict from a label and optional description."""
    return {
        "id": slugify(label),
        "label": label,
        "description": description,
    }
