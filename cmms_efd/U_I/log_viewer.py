
import os
from collections import deque
import streamlit as st

try:
    from streamlit_autorefresh import st_autorefresh
    _HAVE_ST_AUTOREFRESH = True
except Exception:
    _HAVE_ST_AUTOREFRESH = False

LOG_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "backend",
    "main.log"
)

def create_ui():
    """
    Real-time log viewer with options:
    - choose how many last lines to keep visible
    - choose whether to start showing only new lines (tail -f style)
    The view auto-refreshes (requires 'streamlit-autorefresh').
    """
    st.header("Log Viewer — real time")

    if not os.path.exists(LOG_FILE):
        st.error(f"Log file not found: {LOG_FILE}")
        return
    cols = st.columns([1, 1, 2])
    tail_lines = int(cols[0].number_input("Lines to show", min_value=1, max_value=5000, value=200, step=50))
    start_from_end = cols[1].checkbox("Start only new lines (tail -f)", value=False)
    refresh_interval_ms = int(cols[2].number_input("Refresh ms", min_value=200, max_value=10000, value=1000, step=100))
    if _HAVE_ST_AUTOREFRESH:
        st_autorefresh(interval=refresh_interval_ms, key="log_refresh")
    else:
        st.warning("Install 'streamlit-autorefresh' to auto-update without manual refresh: pip install streamlit-autorefresh")
    if "log_text" not in st.session_state:
        st.session_state.log_text = ""
    if "last_pos" not in st.session_state:
        if start_from_end:
            st.session_state.last_pos = os.path.getsize(LOG_FILE)
            st.session_state.log_text = ""
        else:
            with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
                st.session_state.log_text = "".join(deque(f, maxlen=tail_lines))
                st.session_state.last_pos = f.tell()
    try:
        with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
            f.seek(st.session_state.last_pos)
            new_text = f.read()
            if new_text:
                st.session_state.log_text += new_text
            st.session_state.last_pos = f.tell()
    except Exception as e:
        st.error(f"Error reading log file: {e}")
        return
    lines = st.session_state.log_text.splitlines()
    if len(lines) > tail_lines:
        lines = lines[-tail_lines:]
        st.session_state.log_text = "\n".join(lines)
    st.text_area("Live Log", value=st.session_state.log_text, height=600, key="log_area")
    st.write("DEBUG: last_pos=", st.session_state.last_pos, "filesize=", os.path.getsize(LOG_FILE))
