import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText
import threading
import time

LOG_FILE = "main.log"

def create_ui(parent):
    """
    Build the Logs UI inside the given parent frame (for use in tabs).
    """
    frame = ttk.Frame(parent, padding=10)
    frame.pack(fill="both", expand=True)
    text_area = ScrolledText(frame, wrap=tk.WORD, width=100, height=30)
    text_area.pack(fill="both", expand=True)

    def follow_log():
        with open(LOG_FILE, "r") as f:
            f.seek(0, 2)
            while True:
                line = f.readline()
                if line:
                    text_area.insert(tk.END, line)
                    text_area.see(tk.END)
                else:
                    time.sleep(0.2)

    def start_follow():
        t = threading.Thread(target=follow_log, daemon=True)
        t.start()

    btn = ttk.Button(frame, text="Iniciar monitoreo", command=start_follow)
    btn.pack(pady=5)

    return frame
