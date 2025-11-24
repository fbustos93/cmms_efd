from __future__ import annotations

import os
import sys
import panel as pn

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import newSYS
import import_excel_ui
import asset_table
import log_viewer
import plot_interface_catcher

pn.extension()


def create_ui() -> pn.Column:
    """
    Build the main CMMS integration user interface using Panel.
    Returns a Panel object (no server execution here).
    """

    # Placeholder panels with a Load button
    def make_lazy_panel():
        btn = pn.widgets.Button(name="Load", button_type="primary", width=120)
        info = pn.pane.Markdown("Click **Load** to initialize this UI.")
        container = pn.Column(info, btn, sizing_mode="stretch_width")
        return container, btn

    panels = {}
    buttons = {}

    tabs = pn.Tabs(sizing_mode="stretch_width")

    # Create empty panels + buttons for each tab
    for name in [
        "New SYS",
        "Import Excel",
        "Asset Table",
        "Monitoring Data",
        "Plot Catcher",
    ]:
        container, btn = make_lazy_panel()
        panels[name] = container
        buttons[name] = btn
        tabs.append((name, container))

    # Map tab names to loader functions
    loader = {
        "New SYS": newSYS.create_ui,
        "Import Excel": import_excel_ui.create_ui,
        "Asset Table": asset_table.create_ui,
        "Monitoring Data": log_viewer.create_ui,
        "Plot Catcher": plot_interface_catcher.create_ui,
    }

    # Lazy loading handler
    def load_content(event):
        for name, btn in buttons.items():
            if event.obj is btn:
                panels[name].clear()
                try:
                    ui_panel = loader[name]()
                    panels[name].append(ui_panel)
                except Exception as exc:
                    panels[name].append(
                        pn.pane.Markdown(f"**Error loading UI:** {exc}", style={"color": "red"})
                    )

    # Attach callbacks
    for btn in buttons.values():
        btn.on_click(load_content)

    return pn.Column(
        pn.pane.Markdown("## CMMS Integration UI"),
        tabs,
        sizing_mode="stretch_both",
    )
