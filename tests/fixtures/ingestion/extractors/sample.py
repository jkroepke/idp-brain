from pathlib import Path


class Widget:
    def render(self, value: str) -> str:
        return Path(value).name
