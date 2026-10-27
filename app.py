import streamlit as st
import sqlite3
import pandas as pd

# Page Configuration
st.set_page_config(
    page_title="YottaFlex Journey Analytics",
    page_icon="📊",
    layout="wide"
)

# Connect to Database
@st.cache_resource
def get_connection():
    return sqlite3.connect("journey_pipeline.db", check_same_thread=False)

conn = get_connection()

# Sidebar Navigation
st.sidebar.title("🚀 YottaFlex FDE Challenge")
st.sidebar.markdown("**Multi-Channel Customer Journey & Friction Analyzer**")
page = st.sidebar.radio("Navigate to:", ["Funnel & Drop-Offs", "Anomaly & Ground Truth Inspector", "Raw Event Explorer"])

# --- TAB 1: FUNNEL & DROP-OFFS ---
if page == "Funnel & Drop-Offs":
    st.title("📈 Customer Journey Funnel Analysis")
    st.markdown("Analyze drop-off rates and progression across web, mobile app, and support channels.")

    # Query Outcomes / Funnel stages
    df_outcomes = pd.read_sql("SELECT * FROM JourneyOutcome", conn)
    df_sessions = pd.read_sql("SELECT session_id, channel, device_type FROM Session", conn)
    df_merged = df_outcomes.merge(df_sessions, on="session_id")

    col1, col2, col3 = st.columns(3)
    total_sessions = len(df_merged)
    converted = len(df_merged[df_merged["outcome_status"] == "converted"])
    friction = len(df_merged[df_merged["outcome_status"] == "support_friction"])

    col1.metric("Total Sessions", f"{total_sessions:,}")
    col2.metric("Converted Sessions", f"{converted:,}", f"{(converted/total_sessions)*100:.1f}%")
    col3.metric("Support Friction Sessions", f"{friction:,}", f"{(friction/total_sessions)*100:.1f}%")

    st.markdown("---")
    st.subheader("Outcome Status Breakdown by Channel")
    channel_breakdown = pd.crosstab(df_merged["channel"], df_merged["outcome_status"], normalize="index") * 100
    st.bar_chart(channel_breakdown)

# --- TAB 2: ANOMALY & GROUND TRUTH INSPECTOR ---
elif page == "Anomaly & Ground Truth Inspector":
    st.title("🕵️ Anomaly & Ground Truth Inspector")
    st.markdown("Examine the decoupled ground-truth labels for injected edge cases (Bot Traffic, Late Ingestion, Duplicate Conversions, Consent Gaps).")

    try:
        df_gt = pd.read_csv("data/ground_truth/ground_truth.csv")
        st.success(f"Loaded {len(df_gt)} ground-truth anomaly labels successfully!")
        
        # Filter by anomaly type
        anomaly_filter = st.selectbox("Filter by Anomaly Type:", ["All"] + list(df_gt["anomaly_type"].unique()))
        if anomaly_filter != "All":
            df_gt = df_gt[df_gt["anomaly_type"] == anomaly_filter]

        st.dataframe(df_gt, use_container_width=True)
    except FileNotFoundError:
        st.warning("Ground truth file not found. Please run `python generator.py` first.")

# --- TAB 3: RAW DATA EXPLORER ---
elif page == "Raw Event Explorer":
    st.title("🔍 Database Table Explorer")
    st.markdown("Inspect underlying tables stored in SQLite.")

    table_choice = st.selectbox("Select Table:", ["Customer", "Session", "JourneyEvent", "Cart", "Order", "SupportTicket"])
    
    df_table = pd.read_sql(f"SELECT * FROM {table_choice} LIMIT 500", conn)
    st.write(f"Showing up to 500 rows for **{table_choice}**:")
    st.dataframe(df_table, use_container_width=True)