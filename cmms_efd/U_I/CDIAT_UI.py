import streamlit as st
import newSYS
import import_excel_ui
import send_rsp_ui
import asset_table
import log_viewer

st.title("CMMS Integration UI")
tabs = st.tabs(["New SYS", "Import Excel", "Send Data RSP", "Asset Table", "Monitoring Data"])

with tabs[0]:
    st.header("New SYS")
    newSYS.create_ui()

with tabs[1]:
    st.header("Import Excel")
    import_excel_ui.create_ui()

with tabs[2]:
    st.header("Send Data RSP")
    send_rsp_ui.create_ui()

with tabs[3]:
    st.header("Asset Table")
    asset_table.create_ui()

with tabs[4]:
    st.header("Monitoring Data")
    log_viewer.create_ui()
