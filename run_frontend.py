#!/usr/bin/env python3
from __future__ import annotations

"""
Serve the Panel UI only.
No backend started here.
"""

import os
import sys
import panel as pn

ROOT = os.path.abspath(os.path.dirname(__file__))
sys.path.append(os.path.join(ROOT, "U_I"))

from U_I.CDIAT_UI import create_panel


def main() -> None:
    """
    Serve Panel UI at / on localhost.
    """
    layout = create_panel()
    pn.serve(layout, port=8501, show=True, autoreload=False)


if __name__ == "__main__":
    main()
