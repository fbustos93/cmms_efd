import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd
from config_loader import read_config_from_db


def import_from_excel(file_path):
    """
    Import data from Excel and return as a DataFrame.
    """
    try:
        df = pd.read_excel(file_path)
        return df
    except Exception as e:
        messagebox.showerror("Error", f"Failed to import Excel: {e}")
        return pd.DataFrame()


def create_ui(parent):
    """
    Build the Import UI inside the given parent frame (for use in tabs).
    """
    frame = ttk.Frame(parent, padding=10)
    frame.pack(fill="both", expand=True)

    tree = ttk.Treeview(frame, columns=("Name", "Measurement", "Field", "Attribute"), show="headings")
    for col in ("Name", "Measurement", "Field", "Attribute"):
        tree.heading(col, text=col)
        tree.column(col, width=150)

    tree.pack(fill="both", expand=True, pady=5)

    def load_from_excel():
        """Ask user for Excel file and load data into table."""
        file_path = filedialog.askopenfilename(
            filetypes=[("Excel files", "*.xlsx *.xls")]
        )
        if not file_path:
            return
        df = import_from_excel(file_path)
        if not df.empty:
            for row in tree.get_children():
                tree.delete(row)
            for _, row in df.iterrows():
                tree.insert("", "end", values=(
                    row.get("name", ""),
                    row.get("measurement", ""),
                    row.get("field", ""),
                    row.get("attribute", "")
                ))

    def load_from_db():
        """Load data from local DB and display it."""
        configs = read_config_from_db()
        if not configs:
            messagebox.showwarning("No Data", "No configurations found in the DB.")
            return
        for row in tree.get_children():
            tree.delete(row)
        for entry in configs:
            tree.insert("", "end", values=(
                entry.get("name", ""),
                entry.get("measurement", ""),
                entry.get("field", ""),
                entry.get("attribute", "")
            ))

    button_frame = ttk.Frame(frame)
    button_frame.pack(pady=5)

    excel_btn = ttk.Button(button_frame, text="Import from Excel", command=load_from_excel)
    excel_btn.grid(row=0, column=0, padx=5)

    db_btn = ttk.Button(button_frame, text="Load from DB", command=load_from_db)
    db_btn.grid(row=0, column=1, padx=5)

    return frame


if __name__ == "__main__":
    root = tk.Tk()
    root.title("CMMS Data Importer")
    root.geometry("800x400")

    create_ui(root)

    root.mainloop()
