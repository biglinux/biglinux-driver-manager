"""Terminal presentation for big-drivers: colour, emphasis, icons and tables.

Colour only reaches a terminal. Output that goes through a pipe -- the
graphical interface reads this program's output through pkexec, systemd
writes it to the journal -- stays plain text, as does anything run with
NO_COLOR set, TERM=dumb or --color=never.
"""

from __future__ import annotations

import os
import sys
import unicodedata

_mode = "auto"  # auto | always | never


def set_mode(mode: str) -> None:
    global _mode
    _mode = mode


def enabled(stream=None) -> bool:
    if _mode == "always":
        return True
    if _mode == "never":
        return False
    stream = stream or sys.stdout
    if os.environ.get("NO_COLOR") or os.environ.get("TERM") == "dumb":
        return False
    try:
        return stream.isatty()
    except (AttributeError, ValueError):
        return False


_CODES = {
    "bold": "1",
    "dim": "2",
    "italic": "3",
    "underline": "4",
    "red": "31",
    "green": "32",
    "yellow": "33",
    "blue": "34",
    "magenta": "35",
    "cyan": "36",
    "gray": "90",
}


def style(text: str, *names: str, stream=None) -> str:
    if not names or not enabled(stream):
        return text
    codes = ";".join(_CODES[name] for name in names)
    return f"\033[{codes}m{text}\033[0m"


def bold(text: str) -> str:
    return style(text, "bold")


def dim(text: str) -> str:
    return style(text, "dim")


# Icons degrade to ASCII when the terminal cannot show them.
def _icon(fancy: str, plain: str) -> str:
    encoding = (getattr(sys.stdout, "encoding", "") or "").lower()
    return fancy if "utf" in encoding else plain


def ok(text: str) -> str:
    return f"{style(_icon('✔', '+'), 'bold', 'green')} {text}"


def warn(text: str) -> str:
    return f"{style(_icon('⚠', '!'), 'bold', 'yellow')} {text}"


def fail(text: str) -> str:
    return f"{style(_icon('✖', 'x'), 'bold', 'red')} {text}"


def info(text: str) -> str:
    return f"{style(_icon('•', '*'), 'cyan')} {text}"


def step(text: str) -> str:
    return f"{style(_icon('→', '>'), 'bold', 'blue')} {text}"


def bullet_on() -> str:
    return style(_icon("●", "*"), "green")


def bullet_off() -> str:
    return style(_icon("○", "-"), "gray")


def heading(text: str) -> str:
    line = _icon("─", "-") * max(width(text), 8)
    return f"\n{style(text, 'bold', 'cyan')}\n{style(line, 'cyan')}"


def label(name: str, value: str) -> str:
    """'Name: value' with the name in bold, for key/value summaries."""
    return f"  {bold(name + ':')} {value}"


def width(text: str) -> int:
    """Columns a string takes: wide (CJK) characters count twice, escape
    sequences and combining marks count nothing."""
    total, i = 0, 0
    while i < len(text):
        if text[i] == "\033":
            end = text.find("m", i)
            i = len(text) if end == -1 else end + 1
            continue
        char = text[i]
        if not unicodedata.combining(char):
            total += 2 if unicodedata.east_asian_width(char) in ("W", "F") else 1
        i += 1
    return total


def pad(text: str, columns: int) -> str:
    return text + " " * max(columns - width(text), 0)


def table(rows: list[list[str]], indent: int = 2) -> str:
    """Rows of cells aligned in columns (the last column is not padded)."""
    if not rows:
        return ""
    columns = max(len(row) for row in rows)
    widths = [
        max((width(row[c]) for row in rows if c < len(row)), default=0)
        for c in range(columns)
    ]
    lines = []
    for row in rows:
        cells = [
            pad(cell, widths[c]) if c < len(row) - 1 else cell
            for c, cell in enumerate(row)
        ]
        lines.append(" " * indent + "  ".join(cells).rstrip())
    return "\n".join(lines)
