#!/usr/bin/env python3
from __future__ import annotations
import asyncio
import importlib
import os
import sys
from typing import Optional, Any
import panel as pn

BACKEND_MODULE = "backend.main"
BACKEND_FUNC = "main"
FRONTEND_MODULE = "U_I.CDIAT_UI"
FRONTEND_FUNC = "create_panel"

ROOT = os.path.abspath(os.path.dirname(__file__))
sys.path += [ROOT, os.path.join(ROOT, "backend"), os.path.join(ROOT, "U_I")]


def _import_backend():
    """
    Import the backend entrypoint.

    Returns
    -------
    coroutine function or None
        The async function backend.main.main, or None if not found.
    """
    try:
        mod = importlib.import_module(BACKEND_MODULE)
        fn = getattr(mod, BACKEND_FUNC, None)
        return fn if callable(fn) else None
    except Exception:
        return None


def _import_frontend():
    """
    Import the frontend factory.

    Returns
    -------
    callable or None
        The function U_I.CDIAT_UI.create_panel, or None if not found.
    """
    try:
        mod = importlib.import_module(FRONTEND_MODULE)
        fn = getattr(mod, FRONTEND_FUNC, None)
        return fn if callable(fn) else None
    except Exception:
        return None


async def _start_common() -> Optional[Any]:
    """
    Start backend (background) and build frontend layout.

    Returns
    -------
    Panel layout or None
        Frontend layout to be served or shown in notebook.
    """
    backend = _import_backend()
    if backend:
        asyncio.create_task(backend())
        print("[LAUNCHER] Backend started.")
    else:
        print("[LAUNCHER] Backend NOT started (backend.main.main not found).")

    frontend = _import_frontend()
    if not frontend:
        print("[LAUNCHER] Frontend NOT started (U_I.CDIAT_UI.create_panel not found).")
        return None

    layout = frontend()
    return layout


async def start_server(port: Optional[int] = 8501, open_browser: bool = True) -> None:
    """
    Serve Panel UI (non-Jupyter).

    Parameters
    ----------
    port : Optional[int], default 8501
        TCP port for the UI. If None, Panel picks a free port.
    open_browser : bool, default True
        Open the browser automatically.
    """
    layout = await _start_common()
    if layout is None:
        return

    pn.serve(layout, port=port, show=open_browser, autoreload=False) if port \
        else pn.serve(layout, show=open_browser, autoreload=False)


async def start_notebook() -> Optional[Any]:
    """
    Initialize backend and return layout for Jupyter.

    Returns
    -------
    Panel layout or None
        Layout to display directly in a notebook cell.
    """
    return await _start_common()


if __name__ == "__main__":
    asyncio.run(start_server(port=8501, open_browser=True))
