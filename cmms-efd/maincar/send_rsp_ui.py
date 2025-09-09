import tkinter as tk
from tkinter import ttk, messagebox

from config_loader import read_config_from_db
from influx_query import EfdQueryClient


def get_measurements_from_db():
    configs = read_config_from_db()
    return sorted(set(row["measurement"] for row in configs))


def get_fields_from_db(measurement):
    configs = read_config_from_db()
    return sorted(set(row["field"] for row in configs if row["measurement"] == measurement))


def get_config(measurement, field):
    configs = read_config_from_db()
    for row in configs:
        if row["measurement"] == measurement and row["field"] == field:
            return row
    return None


def create_ui(parent):
    """
    Build the Send RSP UI inside the given parent frame (for use in tabs).
    """
    frame = ttk.Frame(parent, padding=10)
    frame.pack(fill="both", expand=True)

    selected_measurement = tk.StringVar()
    selected_field = tk.StringVar()
    interval_value = tk.StringVar()
    limit_value = tk.StringVar()
    ttk.Label(frame, text="Choose telemetry to analyze (Measurement):").pack(pady=5)
    measurement_combo = ttk.Combobox(frame, textvariable=selected_measurement, state="readonly")
    measurement_combo['values'] = get_measurements_from_db()
    measurement_combo.pack()
    ttk.Label(frame, text="Select Field:").pack(pady=5)
    field_combo = ttk.Combobox(frame, textvariable=selected_field, state="readonly")
    field_combo.pack()

    def update_fields(event):
        selected_field.set("")
        fields = get_fields_from_db(selected_measurement.get())
        field_combo['values'] = fields

    measurement_combo.bind("<<ComboboxSelected>>", update_fields)
    ttk.Label(frame, text="Enter Time Interval (e.g., 24h, 2d, 30d):").pack(pady=5)
    ttk.Entry(frame, textvariable=interval_value).pack()
    ttk.Label(frame, text="Enter Limit (number of results):").pack(pady=5)
    ttk.Entry(frame, textvariable=limit_value).pack()

    result_frame = ttk.Frame(frame)
    result_frame.pack(pady=10, fill="both", expand=True)

    def run_query():
        measurement = selected_measurement.get()
        field = selected_field.get()
        interval = interval_value.get()
        limit = limit_value.get()

        if not all([measurement, field, interval, limit]):
            messagebox.showerror("Missing Fields", "Please fill in all inputs.")
            return

        config = get_config(measurement, field)
        if not config:
            messagebox.showerror("Configuration Error", "No matching configuration found in the DB.")
            return

        site = config.get("site", "base")
        db_name = config.get("db_name", "telem")

        try:
            client_efd = EfdQueryClient(site=site, db_name=db_name)
            query = (
                f'SELECT "{field}" FROM "{measurement}" '
                f'WHERE time > now() - {interval} '
                f'ORDER BY time DESC LIMIT {limit}'
            )

            df = client_efd.query(query)

            for widget in result_frame.winfo_children():
                widget.destroy()

            if df.empty:
                messagebox.showinfo("No Data", "Query returned no results.")
                return

            tree = ttk.Treeview(result_frame, columns=list(df.columns), show='headings')
            for col in df.columns:
                tree.heading(col, text=col)
                tree.column(col, width=150)
            for _, row in df.iterrows():
                tree.insert("", "end", values=list(row))

            tree.pack(fill="both", expand=True)

        except Exception as e:
            messagebox.showerror("Query Error", str(e))

    ttk.Button(frame, text="Run Query", command=run_query).pack(pady=10)

    return frame
