import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

import streamlit as st

def main():
    st.title("Tasks & Scheduler")
    
    try:
        from app.scheduler.scheduler import toggle_scheduler, run_job_now
        enabled = st.checkbox("Enable Morning Brief Scheduler")
        toggle_scheduler(enabled)
        
        st.write("Next run: 6:00 AM daily" if enabled else "Scheduler disabled")
        
        if st.button("Run Morning Brief Now"):
            run_job_now("morning_brief")
            st.write("Morning Brief run!")
    except Exception as e:
        st.error(f"Error loading tasks page: {e}")
