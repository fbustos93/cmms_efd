#!/usr/bin/env python3
from __future__ import annotations

"""
Run the backend logic only.
Prints and logs appear directly in the console.
"""

import asyncio
import sys
import os

ROOT = os.path.abspath(os.path.dirname(__file__))
sys.path.append(os.path.join(ROOT, "backend"))

from backend.main import main as backend_main


async def _run() -> None:
    """Execute backend main loop."""
    await backend_main()


if __name__ == "__main__":
    asyncio.run(_run())
