# log_viewer_panel.py
from __future__ import annotations

from pathlib import Path
from collections import deque
from typing import Deque

import panel as pn

from backend.logger_setup import logger, LOG_TIME_FORMAT

LOG_FILE = Path(__file__).resolve().parents[1] / "main.log"


def read_last_lines(path: Path, max_lines: int) -> str:
    """
    Read the last `max_lines` lines from a log file.

    Parameters
    ----------
    path : pathlib.Path
        File path.
    max_lines : int
        Number of lines to return.

    Returns
    -------
    str
        Joined text output.
    """
    if not path.exists():
        return ""

    buffer: Deque[str] = deque(maxlen=max_lines)
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            buffer.append(line)
    return "".join(buffer)


def create_panel() -> pn.Column:
    """
    Construct a live log viewer using periodic updates.

    Returns
    -------
    pn.Column
        Panel layout containing controls and a live text view.
    """
    title = pn.pane.Markdown("### Backend Log — Live View")

    lines_input = pn.widgets.IntInput(name="Lines to keep", value=300, step=50)
    refresh_input = pn.widgets.IntInput(name="Refresh (ms)", value=500, step=100)

    text_box = pn.widgets.TextAreaInput(
        value="",
        height=450,
        disabled=True,
        sizing_mode="stretch_width",
    )

    def update_log() -> None:
        try:
            n = max(int(lines_input.value), 10)
        except Exception:
            n = 300

        try:
            content = read_last_lines(LOG_FILE, n)
            text_box.value = content
        except Exception as exc:
            logger.error(f"{LOG_TIME_FORMAT()} Log update failure: {exc}", exc_info=True)

    pn.state.add_periodic_callback(update_log, period=refresh_input.value, start=True)

    return pn.Column(
        title,
        pn.Row(lines_input, refresh_input),
        text_box,
        sizing_mode="stretch_width",
    )
