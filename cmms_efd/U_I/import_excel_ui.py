import streamlit as st
import pandas as pd
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config_loader import read_config_from_db

def import_from_excel(file_path):
    """
    Import data from Excel and return as a DataFrame.
    """
    try:
        df = pd.read_excel(file_path)
        return df
    except Exception as e:
        st.error(f"Failed to import Excel: {e}")
        return pd.DataFrame()


def create_ui():
    """
    Build the Import Excel UI in Streamlit.
    """
    st.header("Import Excel Data")

    uploaded_file = st.file_uploader("Choose an Excel file", type=["xlsx", "xls"])
    if uploaded_file is not None:
        df = import_from_excel(uploaded_file)
        if not df.empty:
            st.subheader("Imported Excel Data")
            st.dataframe(df[["name", "measurement", "field", "attribute"]].fillna(""))

    if st.button("Load Configurations from DB"):
        configs = read_config_from_db()
        if not configs:
            st.info("No configurations found in the DB.")
        else:
            st.subheader("Configurations from Database")
            table_data = [{
                "name": entry.get("name", ""),
                "measurement": entry.get("measurement", ""),
                "field": entry.get("field", ""),
                "attribute": entry.get("attribute", "")
            } for entry in configs]
            st.table(table_data)


if __name__ == "__main__":
    create_ui()
