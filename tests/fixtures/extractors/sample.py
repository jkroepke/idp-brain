from pathlib import Path


class Widget:
    """Widget docs are untrusted until redaction."""

    def render(self, value):
        """Render a value."""
        return f"{value}:{Path.cwd()}"


def build_widget(name):
    return Widget()
