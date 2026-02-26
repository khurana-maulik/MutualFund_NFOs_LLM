"""
SID Chatbot — Streamlit Frontend (Phase 3)
===========================================
Pre-loaded mutual fund database with fund selector.
No more PDF uploads — data is scraped from AMFI and stored in advance.

Run with:  streamlit run app.py
"""

import streamlit as st
import os

from src.database import init_database, get_all_amcs, get_funds_by_amc, get_fund_by_code, get_fund_count
from src.rag_chain import build_rag_chain, ask_question


# ── Page Configuration ────────────────────────────────────────────────
st.set_page_config(
    page_title="SID Chatbot — Mutual Fund Intelligence Platform",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Main header */
    .main-header {
        text-align: center;
        padding: 1rem 0;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.5rem;
        font-weight: 800;
    }

    .sub-header {
        text-align: center;
        color: #888;
        margin-top: -10px;
        margin-bottom: 20px;
    }

    /* Fund info card */
    .fund-card {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 20px;
        margin: 10px 0;
        color: #e2e8f0;
    }
    .fund-card h3 {
        color: #818cf8;
        margin-bottom: 10px;
    }
    .fund-card .metric {
        display: inline-block;
        margin: 5px 10px 5px 0;
        padding: 4px 12px;
        background: rgba(129, 140, 248, 0.15);
        border-radius: 8px;
        font-size: 0.9em;
    }

    /* Source citation boxes */
    .source-box {
        background-color: #f0f2f6;
        border-left: 4px solid #4CAF50;
        padding: 10px 15px;
        margin: 5px 0;
        border-radius: 0 8px 8px 0;
        font-size: 0.85em;
    }

    /* Status badges */
    .status-ready { color: #4CAF50; font-weight: bold; }
    .status-loading { color: #FF9800; font-weight: bold; }

    /* Sidebar styling */
    .sidebar-stats {
        background: #262730;
        border-radius: 8px;
        padding: 12px;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)


# ── Session State Initialization ──────────────────────────────────────
if "rag_chain" not in st.session_state:
    st.session_state.rag_chain = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "selected_fund_code" not in st.session_state:
    st.session_state.selected_fund_code = None
if "selected_fund_name" not in st.session_state:
    st.session_state.selected_fund_name = ""
if "db_initialized" not in st.session_state:
    init_database()
    st.session_state.db_initialized = True


# ── Check if data exists ──────────────────────────────────────────────
fund_count = get_fund_count()
vectorstore_exists = os.path.exists("vectorstore/index.faiss")


# ── Sidebar: Fund Selector ───────────────────────────────────────────
with st.sidebar:
    st.header("🏦 Mutual Fund Selector")

    if fund_count == 0:
        st.warning("⚠️ No fund data found! Run the setup commands:")
        st.code("""
# Step 1: Scrape NAV data (~20K funds)
python -m scripts.scrape_nav

# Step 2: Enrich with details (top 100 first)
python -m scripts.scrape_scheme_details --limit 100

# Step 3: Build vector store
python -m scripts.ingest_funds
        """, language="bash")
        st.stop()

    # AMC Selector
    amcs = get_all_amcs()
    if not amcs:
        st.error("No AMCs found in database.")
        st.stop()

    selected_amc = st.selectbox(
        "📊 Select Fund House (AMC)",
        options=amcs,
        index=0,
        help="Choose an Asset Management Company"
    )

    # Fund Selector (filtered by AMC)
    if selected_amc:
        funds = get_funds_by_amc(selected_amc)

        if funds:
            # Create display options
            fund_options = {
                f"{f['scheme_name']}": f['scheme_code']
                for f in funds
            }

            selected_fund_name = st.selectbox(
                "💰 Select Fund",
                options=list(fund_options.keys()),
                help="Choose a mutual fund scheme"
            )

            if selected_fund_name:
                selected_code = fund_options[selected_fund_name]

                # If fund changed, reset chat and reload RAG
                if selected_code != st.session_state.selected_fund_code:
                    st.session_state.selected_fund_code = selected_code
                    st.session_state.selected_fund_name = selected_fund_name
                    st.session_state.chat_history = []
                    st.session_state.rag_chain = None  # Force reload
        else:
            st.info(f"No active funds found for {selected_amc}")

    st.divider()

    # Database stats
    st.markdown("### 📈 Database Stats")
    st.metric("Total Funds", f"{fund_count:,}")
    st.metric("AMCs Tracked", f"{len(amcs)}")
    st.metric("Vector Store", "✅ Ready" if vectorstore_exists else "❌ Not Built")

    st.divider()

    # Sample questions
    st.markdown("### 💡 Sample Questions")
    st.markdown("""
    - What is the NAV?
    - What category is this fund?
    - What are the returns?
    - Which fund house manages this?
    - What type of scheme is this?
    """)

    st.divider()

    # Data refresh
    with st.expander("🔄 Data Management"):
        st.caption("Run these commands to update data:")
        st.code("python -m scripts.scrape_nav", language="bash")
        st.code("python -m scripts.scrape_scheme_details --limit 500", language="bash")
        st.code("python -m scripts.ingest_funds", language="bash")


# ── Main Area ─────────────────────────────────────────────────────────

st.markdown("<h1 class='main-header'>🏦 SID Chatbot</h1>", unsafe_allow_html=True)
st.markdown("<p class='sub-header'>Mutual Fund Intelligence Platform — Ask questions about any fund</p>", unsafe_allow_html=True)

# ── Fund Info Card ────────────────────────────────────────────────────
if st.session_state.selected_fund_code:
    fund_info = get_fund_by_code(st.session_state.selected_fund_code)

    if fund_info:
        # Display fund info as columns
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("💰 NAV", f"₹{fund_info.get('net_asset_value', 'N/A')}")
        with col2:
            st.metric("📅 NAV Date", fund_info.get("nav_date", "N/A"))
        with col3:
            st.metric("📂 Category", fund_info.get("scheme_category", "N/A")[:30])
        with col4:
            st.metric("📊 Type", fund_info.get("scheme_type", "N/A")[:25])

        # Fund name banner
        st.info(f"🏦 **{fund_info.get('scheme_name', 'Unknown')}** | {fund_info.get('fund_house', 'Unknown AMC')} | Code: {fund_info.get('scheme_code', 'N/A')}")

    st.divider()

    # ── Load RAG Chain ────────────────────────────────────────────────
    if st.session_state.rag_chain is None and vectorstore_exists:
        with st.spinner("🔄 Loading AI model + vector store..."):
            try:
                from src.embeddings import load_vectorstore
                from langchain_core.documents import Document

                vectorstore = load_vectorstore()

                # Get all documents from the vectorstore for BM25
                # We retrieve a large number to build the BM25 index
                all_docs_with_scores = vectorstore.similarity_search_with_score("", k=1000)
                all_docs = [doc for doc, score in all_docs_with_scores]

                if not all_docs:
                    # Fallback: create a minimal doc list
                    all_docs = [Document(page_content="placeholder", metadata={"page": 0})]

                st.session_state.rag_chain = build_rag_chain(vectorstore, all_docs)
                st.success("✅ AI model loaded and ready!")
            except Exception as e:
                st.error(f"❌ Error loading model: {e}")
                st.info("Make sure to run `python -m scripts.ingest_funds` first.")

    elif not vectorstore_exists:
        st.warning("⚠️ Vector store not built yet. Run: `python -m scripts.ingest_funds`")

    # ── Chat Interface ────────────────────────────────────────────────

    # Display chat history
    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

            if message["role"] == "assistant" and "sources" in message:
                with st.expander("📚 View Source Citations", expanded=False):
                    for i, source in enumerate(message["sources"], 1):
                        score = source.get("score", 0.0)
                        st.markdown(
                            f"**Source {i}** — Page {source['page']} ({source['type']}) | Score: {score:.2f}"
                        )
                        st.text(source["text"][:300] + "...")
                        st.divider()

    # Chat input
    user_question = st.chat_input(
        f"Ask about {st.session_state.selected_fund_name[:50]}..." if st.session_state.selected_fund_name else "Select a fund first..."
    )

    if user_question:
        if st.session_state.rag_chain is None:
            st.error("Please wait for the AI model to load, or build the vector store first.")
        else:
            # Display user message
            with st.chat_message("user"):
                st.markdown(user_question)

            st.session_state.chat_history.append({
                "role": "user",
                "content": user_question,
            })

            # Get answer
            with st.chat_message("assistant"):
                with st.spinner("🤔 Searching and generating answer..."):
                    try:
                        # Prepend fund context to the question
                        enriched_question = f"[Fund: {st.session_state.selected_fund_name}] {user_question}"
                        result = ask_question(st.session_state.rag_chain, enriched_question)

                        # Display confidence
                        confidence = result.get("confidence", {})
                        if confidence:
                            level = confidence.get("level", "UNKNOWN")
                            score = confidence.get("score", 0.0)
                            emoji = {"HIGH": "🟢", "MEDIUM": "🟡", "LOW": "🔴"}.get(level, "⚪")
                            st.markdown(f"{emoji} **Confidence: {level}** ({score:.2f})")
                            st.caption(confidence.get("explanation", ""))

                        # Display answer
                        st.markdown(result["answer"])

                        # Display sources
                        if result["sources"]:
                            with st.expander("📚 View Source Citations", expanded=False):
                                for i, source in enumerate(result["sources"], 1):
                                    score = source.get("score", 0.0)
                                    st.markdown(
                                        f"**Source {i}** — Page {source['page']} ({source['type']}) | Score: {score:.2f}"
                                    )
                                    st.text(source["text"][:300] + "...")
                                    st.divider()

                        st.session_state.chat_history.append({
                            "role": "assistant",
                            "content": result["answer"],
                            "sources": result["sources"],
                            "confidence": confidence,
                        })

                    except Exception as e:
                        error_msg = f"❌ Error: {str(e)}"
                        st.error(error_msg)
                        st.session_state.chat_history.append({
                            "role": "assistant",
                            "content": error_msg,
                        })

else:
    st.info("👈 Select a fund from the sidebar to start asking questions.")
