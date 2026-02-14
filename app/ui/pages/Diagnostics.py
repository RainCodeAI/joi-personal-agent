import streamlit as st
from app.memory.store import MemoryStore, SQLSession, engine
from app.config import settings
import httpx
import requests  # For endpoint calls
from sqlalchemy import text
from pathlib import Path
import time

def main():
    st.title("🔧 Diagnostics")
    st.markdown("Check Joi's health, DB status, and performance.")

    # Quick Status
    try:
        with SQLSession(engine) as session:
            session.execute(text("SELECT 1"))
        db_ok = True
        db_error = ""
    except Exception as e:
        db_ok = False
        db_error = str(e)

    st.subheader("Quick Status")
    status_color = "#133d13" if db_ok else "#5a1111"
    border_color = "#1f7a1f" if db_ok else "#a11d1d"
    indicator = "🟢" if db_ok else "🔴"
    message = "DB Connection OK" if db_ok else "DB Connection Error"
    st.markdown(
        f"""
        <div style="padding:12px 16px; border-radius:10px; border:1px solid {border_color}; background-color:{status_color}; color:#f0f0f0;">
            <strong>{indicator} {message}</strong>
        </div>
        """,
        unsafe_allow_html=True
    )

    # DB Connection Check
    st.subheader("Database Connection")
    if db_ok:
        st.success("✅ DB Connected")
    else:
        st.error(f"❌ DB Error: {db_error}")

    # DB URL (redacted)
    db_url = settings.database_url
    if db_url:
        redacted = db_url.replace(db_url.split('@')[0].split('//')[1], 'joi_user:***')
        st.write(f"**DB URL**: {redacted}")
    else:
        st.write("**DB URL**: Not set")

    # Extensions
    st.subheader("Extensions")
    extensions = ["uuid-ossp", "vector"]
    for ext in extensions:
        try:
            with SQLSession(engine) as session:
                result = session.execute(text(f"SELECT * FROM pg_extension WHERE extname = '{ext}'")).fetchone()
            if result:
                st.success(f"✅ {ext} installed")
            else:
                st.warning(f"⚠️ {ext} not installed")
        except Exception as e:
            st.error(f"❌ {ext} check failed: {e}")

    # Indexes — expanded to check all performance indexes
    st.subheader("Indexes")
    indexes = [
        ("ix_memory_embedding", "memory"),
        ("ix_memory_type_created", "memory"),
        ("ix_entity_name_type", "entity"),
        ("ix_entity_embedding_ivfflat", "entity"),
        ("ix_rel_from_to", "relationship"),
        ("ix_rel_type", "relationship"),
        ("ix_chat_session_ts", "chatmessage"),
        ("ix_mood_user_date", "moodentry"),
    ]
    idx_cols = st.columns(2)
    for i, (idx_name, table_name) in enumerate(indexes):
        col = idx_cols[i % 2]
        try:
            with SQLSession(engine) as session:
                result = session.execute(text(f"SELECT * FROM pg_indexes WHERE indexname = '{idx_name}'")).fetchone()
            if result:
                col.success(f"✅ {idx_name}")
            else:
                col.warning(f"⚠️ {idx_name} missing")
        except Exception as e:
            col.error(f"❌ {idx_name}: {e}")

    # Row Counts — expanded with entity/relationship/contacts tables
    st.subheader("Row Counts")
    tables = [
        "memory", "chatmessage", "moodentry", "habit", "decision",
        "personalgoal", "cbtexercise", "entity", "relationship",
        "contacts", "sleep_log", "transactions"
    ]
    count_cols = st.columns(3)
    for i, table in enumerate(tables):
        col = count_cols[i % 3]
        try:
            with SQLSession(engine) as session:
                result = session.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
            col.metric(table, f"{result:,}")
        except Exception as e:
            col.error(f"❌ {table}: {e}")

    # Table Stats — pg_stat_user_tables
    st.subheader("Table Performance Stats")
    st.caption("Sequential vs. index scans, dead tuples (from pg_stat_user_tables)")
    try:
        with SQLSession(engine) as session:
            stats = session.execute(text("""
                SELECT relname, seq_scan, idx_scan,
                       n_live_tup, n_dead_tup,
                       last_vacuum, last_autovacuum
                FROM pg_stat_user_tables
                ORDER BY seq_scan DESC
            """)).fetchall()
        if stats:
            import pandas as pd
            df = pd.DataFrame(stats, columns=[
                "Table", "Seq Scans", "Idx Scans",
                "Live Rows", "Dead Rows",
                "Last Vacuum", "Last Autovacuum"
            ])
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No table stats available.")
    except Exception as e:
        st.error(f"Stats query failed: {e}")

    # Query Timing — benchmark key queries
    st.subheader("Query Benchmarks")
    if st.button("Run Benchmarks"):
        benchmarks = {
            "Memory by type": "SELECT COUNT(*) FROM memory WHERE type = 'user_input'",
            "Chat history lookup": "SELECT COUNT(*) FROM chatmessage WHERE session_id = 'default'",
            "Mood trend": "SELECT AVG(mood) FROM moodentry WHERE user_id = 'default'",
            "Entity lookup": "SELECT COUNT(*) FROM entity WHERE name IS NOT NULL",
            "Relationship traversal": "SELECT COUNT(*) FROM relationship",
        }
        for label, query in benchmarks.items():
            try:
                with SQLSession(engine) as session:
                    t0 = time.perf_counter()
                    session.execute(text(query)).fetchall()
                    elapsed = (time.perf_counter() - t0) * 1000
                color = "green" if elapsed < 50 else "orange" if elapsed < 200 else "red"
                st.markdown(f":{color}[**{label}**]: `{elapsed:.1f}ms`")
            except Exception as e:
                st.error(f"❌ {label}: {e}")

    # ANALYZE Button
    if st.button("Run ANALYZE on Tables"):
        try:
            with SQLSession(engine) as session:
                for table in tables:
                    session.execute(text(f"ANALYZE {table}"))
                session.commit()
            st.success("✅ ANALYZE completed")
        except Exception as e:
            st.error(f"❌ ANALYZE failed: {e}")

    # Health Checks
    st.subheader("Health Checks")
    # DB Health
    if db_ok:
        st.success("✅ DB Health OK")
    else:
        st.error(f"❌ DB Health: {db_error}")

    # Ollama Health
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(f"{settings.ollama_host}/api/tags")
            if response.status_code == 200:
                st.success("✅ Ollama Health OK")
            else:
                st.warning(f"⚠️ Ollama status: {response.status_code}")
    except Exception as e:
        st.error(f"❌ Ollama Health: {e}")

    # Chroma Health (basic heartbeat)
    memory_store = MemoryStore()
    try:
        memory_store.chroma_client.heartbeat()
        st.success("✅ Chroma Health OK")
    except Exception as e:
        st.warning(f"⚠️ Chroma Health: {e}")

    # Chroma Detailed Health (via endpoint)
    st.subheader("Chroma Health")
    try:
        resp = requests.get("http://localhost:8000/diagnostics/chroma/health").json()
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Collection", resp["name"])
        with col2:
            st.metric("Item Count", resp["count"])
        with col3:
            dim = resp["embed_dim_meta"]
            st.metric("Embed Dim", dim, delta=f"Expected: {settings.embed_dim}" if dim == str(settings.embed_dim) else "MISMATCH!")
        if int(dim) != settings.embed_dim:
            st.error("Run reset_chroma.py!")
    except Exception as e:
        st.error(f"Health check failed: {e}")

    # Fallback Status Banner
    st.subheader("AI Fallback Status")
    try:
        # Simple Ollama ping
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(f"{settings.ollama_host}/api/tags")
            provider = "Ollama (Local)" if resp.status_code == 200 else "Fallback (GPT/Grok/Gemini)"
            st.success(f"Active Provider: {provider}")
    except Exception as e:
        st.warning(f"Provider check: {e} – Fallback active")

    # ── Scheduler & Jobs Debug ────────────────────────────────────────
    st.subheader("⏰ Scheduler & Jobs")
    st.caption("Manually trigger proactive checks to test the logic.")
    
    jcol1, jcol2 = st.columns(2)
    with jcol1:
        if st.button("Run Mood Check Now"):
            from app.scheduler.jobs import check_mood_trends
            msg = check_mood_trends()
            if msg:
                st.success(f"Triggered! Message: {msg}")
            else:
                st.info("No mood nudge needed (trends look ok).")
    
    with jcol2:
        if st.button("Run Habit Check Now"):
            from app.scheduler.jobs import check_habits
            msg = check_habits()
            if msg:
                st.success(f"Triggered! Message: {msg}")
            else:
                st.info("No habit nudge needed.")

    # Real-Time Log Streaming
    st.subheader("📜 Real-Time Logs")

    log_files = {
        "Router Logs": "data/router_logs.jsonl",
        "Action Ledger": "data/action_ledger.jsonl",
    }

    log_col1, log_col2 = st.columns([2, 1])
    with log_col1:
        selected_log = st.selectbox("Log Source", list(log_files.keys()))
    with log_col2:
        tail_n = st.slider("Lines", 5, 50, 15, key="log_tail_n")

    auto_refresh = st.checkbox("Auto-refresh (5s)", value=False)
    if auto_refresh:
        try:
            from streamlit_autorefresh import st_autorefresh
            st_autorefresh(interval=5000, limit=None, key="log_refresh")
        except ImportError:
            st.caption("Install `streamlit-autorefresh` for auto-refresh. Refresh page manually.")

    log_path = Path(log_files[selected_log])
    if log_path.exists():
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            tail = lines[-tail_n:] if len(lines) > tail_n else lines
            st.caption(f"Showing last {len(tail)} of {len(lines)} entries")
            
            import json as _json
            for line in reversed(tail):
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = _json.loads(line)
                    ts = entry.get("ts", "")[:19]
                    has_error = bool(entry.get("error"))
                    
                    if selected_log == "Router Logs":
                        provider = entry.get("provider", "?")
                        prompt_len = entry.get("prompt_len", "?")
                        label = f"`{ts}` · **{provider}** · prompt: {prompt_len} chars"
                    else:
                        action = entry.get("action", "?")
                        label = f"`{ts}` · **{action}**"
                    
                    if has_error:
                        st.markdown(f":red[⚠ {label}]")
                        st.code(entry["error"], language="text")
                    else:
                        st.markdown(f":green[✓] {label}")
                except _json.JSONDecodeError:
                    st.text(line)
        except Exception as e:
            st.error(f"Failed to read log: {e}")
    else:
        st.info(f"No log file found at `{log_path}`. It will appear after the first agent interaction.")

    # ── Agent Decision Traces ─────────────────────────────────────────
    st.subheader("🧠 Agent Decision Traces")
    st.caption("Structured trace of each orchestrator call: which sub-agents ran, latency, tools used, and any prompt-injection threats detected.")

    trace_path = Path("data/agent_traces.jsonl")
    if trace_path.exists():
        try:
            import json as _json
            with open(trace_path, 'r', encoding='utf-8') as f:
                all_traces = [_json.loads(l) for l in f if l.strip()]

            if all_traces:
                recent_traces = list(reversed(all_traces[-20:]))
                st.caption(f"Showing latest {len(recent_traces)} of {len(all_traces)} traces")

                for trace in recent_traces:
                    ts = trace.get("timestamp", "")[:19]
                    latency = trace.get("latency_ms", "?")
                    agents = ", ".join(trace.get("sub_agents_invoked", []))
                    tools = trace.get("tool_calls", [])
                    threats = trace.get("threats_detected", [])

                    threat_badge = f"  :red[⚠ {len(threats)} threat(s)]" if threats else ""
                    tool_badge = f"  🔧 {len(tools)} tool(s)" if tools else ""

                    with st.expander(f"`{ts}` · **{latency}ms**{tool_badge}{threat_badge}"):
                        st.markdown(f"**Sub-agents**: {agents}")
                        st.markdown(f"**Latency**: {latency}ms")

                        if threats:
                            st.warning(f"Threats detected: {', '.join(threats)}")

                        if tools:
                            st.markdown("**Tool Calls:**")
                            for tc in tools:
                                st.code(_json.dumps(tc, indent=2), language="json")

                        ctx = trace.get("context_summary", "")
                        if ctx:
                            st.markdown("**Context (first 200 chars):**")
                            st.text(ctx)

                        resp = trace.get("llm_response_preview", "")
                        if resp:
                            st.markdown("**LLM Response (first 200 chars):**")
                            st.text(resp)
            else:
                st.info("No traces recorded yet.")
        except Exception as e:
            st.error(f"Failed to read traces: {e}")
    else:
        st.info("No trace file found. Traces will appear after the first chat interaction with the refactored agent.")

    # ── Benchmark Baseline Save / Compare ─────────────────────────────
    st.subheader("📊 Benchmark Baseline")
    baseline_path = Path("data/benchmark_baseline.json")

    bcol1, bcol2 = st.columns(2)
    with bcol1:
        if st.button("💾 Save Current as Baseline"):
            benchmarks = {
                "Memory by type": "SELECT COUNT(*) FROM memory WHERE type = 'user_input'",
                "Chat history lookup": "SELECT COUNT(*) FROM chatmessage WHERE session_id = 'default'",
                "Mood trend": "SELECT AVG(mood) FROM moodentry WHERE user_id = 'default'",
                "Entity lookup": "SELECT COUNT(*) FROM entity WHERE name IS NOT NULL",
                "Relationship traversal": "SELECT COUNT(*) FROM relationship",
            }
            import json as _json
            results = {}
            for label, query in benchmarks.items():
                try:
                    with SQLSession(engine) as session:
                        t0 = time.perf_counter()
                        session.execute(text(query)).fetchall()
                        elapsed = round((time.perf_counter() - t0) * 1000, 2)
                    results[label] = elapsed
                except Exception as e:
                    results[label] = f"error: {e}"
            results["_saved_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            baseline_path.parent.mkdir(parents=True, exist_ok=True)
            with open(baseline_path, "w") as f:
                _json.dump(results, f, indent=2)
            st.success("Baseline saved!")

    with bcol2:
        if baseline_path.exists():
            import json as _json
            with open(baseline_path) as f:
                baseline = _json.load(f)
            saved_at = baseline.pop("_saved_at", "unknown")
            st.caption(f"Baseline saved at: {saved_at}")
            for label, ms in baseline.items():
                st.metric(label, f"{ms}ms" if isinstance(ms, (int, float)) else ms)