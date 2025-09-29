import streamlit as st
from config_loader import read_config_from_db
from influx_query import EfdQueryClient

def get_measurements_from_db():
    """Return sorted list of unique measurements from the DB."""
    configs = read_config_from_db()
    return sorted(set(row["measurement"] for row in configs))

def get_fields_from_db(measurement):
    """Return sorted list of fields for a given measurement."""
    configs = read_config_from_db()
    return sorted(set(row["field"] for row in configs if row["measurement"] == measurement))

def get_config(measurement, field):
    """Return the configuration dict for a given measurement and field."""
    configs = read_config_from_db()
    for row in configs:
        if row["measurement"] == measurement and row["field"] == field:
            return row
    return None

def create_ui():
    """
    Streamlit UI for Send Data to RSP, replicating Tkinter behavior.
    Select measurement and field, enter interval and limit, then run query.
    """
    st.header("Send Data to RSP")
    if "selected_measurement" not in st.session_state:
        st.session_state.selected_measurement = ""
    if "selected_field" not in st.session_state:
        st.session_state.selected_field = ""
    if "interval" not in st.session_state:
        st.session_state.interval = ""
    if "limit" not in st.session_state:
        st.session_state.limit = ""
    st.subheader("Choose Telemetry Measurement")
    measurements = get_measurements_from_db()
    st.session_state.selected_measurement = st.selectbox(
        "Measurement",
        [""] + measurements,
        index=0
    )

    st.subheader("Select Field")
    fields = get_fields_from_db(st.session_state.selected_measurement) if st.session_state.selected_measurement else []
    st.session_state.selected_field = st.selectbox(
        "Field",
        [""] + fields,
        index=0
    )

    st.text_input("Enter Time Interval (e.g., 24h, 2d, 30d):", key="interval")
    st.text_input("Enter Limit (number of results):", key="limit")
    if st.button("Run Query"):
        measurement = st.session_state.selected_measurement
        field = st.session_state.selected_field
        interval = st.session_state.interval
        limit = st.session_state.limit
        if not all([measurement, field, interval, limit]):
            st.error("Please fill in all inputs.")
        else:
            config = get_config(measurement, field)
            if not config:
                st.error("No matching configuration found in the DB.")
            else:
                site = config.get("site", "base")
                db_name = config.get("db_name", "telem")
                try:
                    client_efd = EfdQueryClient(site=site, db_name=db_name)
                    query = f'SELECT "{field}" FROM "{measurement}" WHERE time > now() - {interval} ORDER BY time DESC LIMIT {limit}'
                    df = client_efd.query(query)

                    if df.empty:
                        st.info("Query returned no results.")
                    else:
                        st.dataframe(df)

                except Exception as e:
                    st.error(f"Query Error: {e}")
