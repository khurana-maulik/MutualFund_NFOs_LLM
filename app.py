"""
SID Chatbot — Streamlit Frontend (Phase 5)
===========================================
Premium Mutual Fund Intelligence Platform with authentication.
Features: Login/Signup with glassmorphism UI, fund selector, hybrid RAG.

Run with:  streamlit run app.py
"""

import streamlit as st
import os

from src.database import (
    init_database, get_all_amcs, get_funds_by_amc,
    get_fund_by_code, get_fund_count, search_funds_global,
    get_data_freshness, get_enriched_fund_count,
)
from src.rag_chain import build_rag_chain, ask_question
from src.auth import create_users_table, register_user, authenticate_user


# ── Page Configuration ────────────────────────────────────────────────
st.set_page_config(
    page_title="SID Chatbot — Mutual Fund Intelligence Platform",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ── Initialize Database + Auth ────────────────────────────────────────
if "db_initialized" not in st.session_state:
    try:
        init_database()
        create_users_table()
        st.session_state.db_initialized = True
    except Exception as e:
        st.error(f"Database initialization failed: {e}")
        st.stop()


# ── Google OAuth Initialization ───────────────────────────────────────
import json
from src.config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI

# Write temp credentials file if env vars are present
if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET:
    creds = {
        "web": {
            "client_id": GOOGLE_CLIENT_ID,
            "project_id": "sid-chatbot",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uris": [GOOGLE_REDIRECT_URI]
        }
    }
    with open("google_credentials.json", "w") as f:
        json.dump(creds, f)

has_google_auth = os.path.exists("google_credentials.json")
authenticator = None

if has_google_auth:
    from streamlit_google_auth import Authenticate
    authenticator = Authenticate(
        secret_credentials_path='google_credentials.json',
        cookie_name='sid_chatbot_auth',
        cookie_key='this_is_secret',
        redirect_uri=GOOGLE_REDIRECT_URI,
    )
    # Check if returning from Google redirect
    authenticator.check_authentification()
    if st.session_state.get("connected"):
        st.session_state.authenticated = True
        user_info = st.session_state.get("user_info", {})
        st.session_state.user = {
            "id": user_info.get("id", "google_user"),
            "username": user_info.get("name", "Google User"),
            "email": user_info.get("email", ""),
            "created_at": "N/A",
            "last_login": "Now (Google SSO)"
        }


# ── Session State Initialization ──────────────────────────────────────
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user" not in st.session_state:
    st.session_state.user = None
if "rag_chain" not in st.session_state:
    st.session_state.rag_chain = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "selected_fund_code" not in st.session_state:
    st.session_state.selected_fund_code = None
if "selected_fund_name" not in st.session_state:
    st.session_state.selected_fund_name = ""


# ══════════════════════════════════════════════════════════════════════
#                          LOGIN / SIGNUP PAGE
# ══════════════════════════════════════════════════════════════════════

def show_login_page():
    """Render the premium glassmorphism login/signup page."""

    # ── Full-page CSS for login ──────────────────────────────────────
    st.markdown("""
    <style>
        /* Hide Streamlit default elements for clean login page */
        #MainMenu {visibility: hidden;}
        header {visibility: hidden;}
        footer {visibility: hidden;}
        .stDeployButton {display: none;}

        /* Animated gradient background */
        .stApp {
            background: linear-gradient(-45deg, #0f0c29, #302b63, #24243e, #0f0c29);
            background-size: 400% 400%;
            animation: gradientShift 15s ease infinite;
        }

        @keyframes gradientShift {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }

        /* Glass card container */
        .glass-card {
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 24px;
            padding: 40px 36px;
            max-width: 480px;
            margin: 40px auto;
            box-shadow:
                0 8px 32px rgba(0, 0, 0, 0.3),
                inset 0 1px 0 rgba(255, 255, 255, 0.1);
        }

        /* Logo styling */
        .login-logo {
            text-align: center;
            font-size: 3.5rem;
            margin-bottom: 8px;
            animation: float 3s ease-in-out infinite;
        }

        @keyframes float {
            0%, 100% { transform: translateY(0px); }
            50% { transform: translateY(-8px); }
        }

        .login-title {
            text-align: center;
            font-size: 2rem;
            font-weight: 800;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 4px;
        }

        .login-subtitle {
            text-align: center;
            color: rgba(255, 255, 255, 0.5);
            font-size: 0.95rem;
            margin-bottom: 30px;
            letter-spacing: 0.5px;
        }

        /* Premium input fields */
        .stTextInput > div > div > input {
            background: rgba(255, 255, 255, 0.06) !important;
            border: 1px solid rgba(255, 255, 255, 0.12) !important;
            border-radius: 12px !important;
            color: #e2e8f0 !important;
            padding: 14px 16px !important;
            font-size: 0.95rem !important;
            transition: all 0.3s ease !important;
        }

        .stTextInput > div > div > input:focus {
            border-color: rgba(102, 126, 234, 0.6) !important;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.15) !important;
            background: rgba(255, 255, 255, 0.08) !important;
        }

        .stTextInput > div > div > input::placeholder {
            color: rgba(255, 255, 255, 0.3) !important;
        }

        /* Input labels */
        .stTextInput > label {
            color: rgba(255, 255, 255, 0.7) !important;
            font-weight: 500 !important;
            font-size: 0.85rem !important;
            letter-spacing: 0.3px !important;
        }

        /* Premium button */
        .stButton > button {
            width: 100%;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
            color: white !important;
            border: none !important;
            border-radius: 12px !important;
            padding: 14px 24px !important;
            font-size: 1rem !important;
            font-weight: 600 !important;
            letter-spacing: 0.5px !important;
            cursor: pointer !important;
            transition: all 0.3s ease !important;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3) !important;
            margin-top: 8px !important;
        }

        .stButton > button:hover {
            transform: translateY(-2px) !important;
            box-shadow: 0 6px 20px rgba(102, 126, 234, 0.5) !important;
        }

        .stButton > button:active {
            transform: translateY(0px) !important;
        }

        /* Tabs styling */
        .stTabs [data-baseweb="tab-list"] {
            gap: 0px;
            background: rgba(255, 255, 255, 0.04);
            border-radius: 14px;
            padding: 4px;
            border: 1px solid rgba(255, 255, 255, 0.06);
        }

        .stTabs [data-baseweb="tab"] {
            border-radius: 10px;
            color: rgba(255, 255, 255, 0.5);
            font-weight: 600;
            padding: 10px 24px;
            font-size: 0.9rem;
            letter-spacing: 0.3px;
        }

        .stTabs [aria-selected="true"] {
            background: rgba(102, 126, 234, 0.25) !important;
            color: #a5b4fc !important;
        }

        .stTabs [data-baseweb="tab-border"] {
            display: none;
        }

        .stTabs [data-baseweb="tab-highlight"] {
            display: none;
        }

        /* Alert styling */
        .stAlert {
            border-radius: 12px !important;
        }

        /* Feature pills row */
        .features-row {
            display: flex;
            justify-content: center;
            gap: 10px;
            flex-wrap: wrap;
            margin-top: 24px;
        }
        .feature-pill {
            background: rgba(255, 255, 255, 0.06);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 20px;
            padding: 6px 14px;
            font-size: 0.75rem;
            color: rgba(255, 255, 255, 0.5);
            letter-spacing: 0.3px;
        }

        /* Divider styling */
        .login-divider {
            display: flex;
            align-items: center;
            gap: 12px;
            margin: 20px 0;
            color: rgba(255, 255, 255, 0.25);
            font-size: 0.8rem;
        }
        .login-divider::before,
        .login-divider::after {
            content: '';
            flex: 1;
            height: 1px;
            background: rgba(255, 255, 255, 0.1);
        }

        /* Hide sidebar on login page */
        [data-testid="stSidebar"] {
            display: none;
        }
    </style>
    """, unsafe_allow_html=True)

    # ── Glass Card Layout ────────────────────────────────────────────
    col_left, col_center, col_right = st.columns([1, 2, 1])

    with col_center:
        st.markdown("""
            <div class="login-logo">🏦</div>
            <div class="login-title">SID Chatbot</div>
            <div class="login-subtitle">Mutual Fund Intelligence Platform</div>
        """, unsafe_allow_html=True)

        # Login / Sign Up Tabs
        tab_login, tab_signup = st.tabs(["🔑  Login", "✨  Sign Up"])

        # ── Login Tab ────────────────────────────────────────────────
        with tab_login:
            with st.form("login_form", clear_on_submit=False):
                login_email = st.text_input(
                    "Email Address",
                    placeholder="you@example.com",
                    key="login_email"
                )
                login_password = st.text_input(
                    "Password",
                    type="password",
                    placeholder="Enter your password",
                    key="login_password"
                )

                login_submitted = st.form_submit_button("Sign In →")

                if login_submitted:
                    result = authenticate_user(login_email, login_password)
                    if result["success"]:
                        st.session_state.authenticated = True
                        st.session_state.user = result["user"]
                        st.rerun()
                    else:
                        st.error(f"❌ {result['error']}")

        # ── Sign Up Tab ──────────────────────────────────────────────
        with tab_signup:
            with st.form("signup_form", clear_on_submit=True):
                signup_name = st.text_input(
                    "Full Name",
                    placeholder="Maulik Khurana",
                    key="signup_name"
                )
                signup_email = st.text_input(
                    "Email Address",
                    placeholder="you@example.com",
                    key="signup_email"
                )
                signup_password = st.text_input(
                    "Create Password",
                    type="password",
                    placeholder="Min. 6 characters",
                    key="signup_password"
                )
                signup_confirm = st.text_input(
                    "Confirm Password",
                    type="password",
                    placeholder="Re-enter your password",
                    key="signup_confirm"
                )

                signup_submitted = st.form_submit_button("Create Account →")

                if signup_submitted:
                    if signup_password != signup_confirm:
                        st.error("❌ Passwords do not match.")
                    else:
                        result = register_user(signup_name, signup_email, signup_password)
                        if result["success"]:
                            st.success("✅ Account created! Please switch to the Login tab to sign in.")
                        else:
                            st.error(f"❌ {result['error']}")

        # Feature pills
        st.markdown("""
            <div class="features-row">
                <span class="feature-pill">🤖 AI-Powered RAG</span>
                <span class="feature-pill">📊 14K+ Funds</span>
                <span class="feature-pill">🔍 Hybrid Search</span>
                <span class="feature-pill">🏦 35+ AMCs</span>
            </div>
        """, unsafe_allow_html=True)

        if authenticator:
            st.markdown('<div class="login-divider">OR CONTINUE WITH</div>', unsafe_allow_html=True)
            authenticator.login()


# ══════════════════════════════════════════════════════════════════════
#                          MAIN APPLICATION
# ══════════════════════════════════════════════════════════════════════

def show_main_app():
    """Render the main chatbot application (post-login)."""

    # ── Custom CSS for main app ──────────────────────────────────────
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

        /* Freshness indicator */
        .freshness-good { color: #4CAF50; }
        .freshness-stale { color: #FF9800; }
        .freshness-old { color: #f44336; }

        /* User profile badge */
        .user-badge {
            background: linear-gradient(135deg, rgba(102, 126, 234, 0.15), rgba(118, 75, 162, 0.15));
            border: 1px solid rgba(102, 126, 234, 0.25);
            border-radius: 12px;
            padding: 12px 16px;
            margin-bottom: 16px;
            text-align: center;
        }
        .user-badge .user-name {
            color: #a5b4fc;
            font-weight: 700;
            font-size: 1.05rem;
        }
        .user-badge .user-email {
            color: rgba(255, 255, 255, 0.4);
            font-size: 0.8rem;
            margin-top: 2px;
        }
    </style>
    """, unsafe_allow_html=True)

    # ── Check if data exists ─────────────────────────────────────────
    try:
        fund_count = get_fund_count()
    except Exception:
        fund_count = 0

    vectorstore_exists = os.path.exists("vectorstore/index.faiss")

    # ── Sidebar: User Profile + Fund Selector ────────────────────────
    with st.sidebar:
        # User profile badge
        user = st.session_state.user
        st.markdown(f"""
            <div class="user-badge">
                <div class="user-name">👋 {user['username']}</div>
                <div class="user-email">{user['email']}</div>
            </div>
        """, unsafe_allow_html=True)

        # Logout button
        if st.button("🚪 Logout", use_container_width=True):
            if "authenticator" in globals() and authenticator and st.session_state.get("connected"):
                authenticator.logout()
            
            st.session_state.authenticated = False
            st.session_state.user = None
            st.session_state.rag_chain = None
            st.session_state.chat_history = []
            st.session_state.selected_fund_code = None
            st.session_state.selected_fund_name = ""
            st.rerun()

        st.divider()
        st.header("🏦 Mutual Fund Selector")

        if fund_count == 0:
            st.warning("⚠️ No fund data found! Run the setup commands:")
            st.code("""
# Step 1: Scrape NAV data (~14K funds)
python -m scripts.scrape_nav

# Step 2: Enrich with details (top 500)
python -m scripts.scrape_scheme_details --limit 500

# Step 3: Build vector store
python -m scripts.ingest_funds --texts-only
            """, language="bash")
            st.stop()

        # ── Global Fund Search ───────────────────────────────────────
        st.markdown("#### 🔍 Quick Search")
        search_query = st.text_input(
            "Search any fund by name",
            placeholder="e.g. HDFC Flexi Cap, Midcap, SBI...",
            help="Search across all 14K+ funds by name, AMC, or category",
            key="global_search"
        )

        if search_query and len(search_query) >= 2:
            search_results = search_funds_global(search_query, limit=15)
            if search_results:
                search_options = {
                    f"{r['scheme_name'][:60]} ({r['fund_house'][:20]})": r['scheme_code']
                    for r in search_results
                }
                selected_search = st.selectbox(
                    f"Found {len(search_results)} funds:",
                    options=list(search_options.keys()),
                    key="search_results_select"
                )
                if selected_search:
                    code = search_options[selected_search]
                    if code != st.session_state.selected_fund_code:
                        st.session_state.selected_fund_code = code
                        st.session_state.selected_fund_name = selected_search.split(" (")[0]
                        st.session_state.chat_history = []
                        st.session_state.rag_chain = None
            else:
                st.caption("No funds found for this search.")

        st.divider()

        # ── AMC + Fund Dropdown ──────────────────────────────────────
        st.markdown("#### 📊 Browse by AMC")
        amcs = get_all_amcs()
        if not amcs:
            st.error("No AMCs found in database.")
            st.stop()

        selected_amc = st.selectbox(
            "Select Fund House (AMC)",
            options=amcs,
            index=0,
            help="Choose an Asset Management Company"
        )

        if selected_amc:
            funds = get_funds_by_amc(selected_amc)

            if funds:
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

                    if selected_code != st.session_state.selected_fund_code:
                        st.session_state.selected_fund_code = selected_code
                        st.session_state.selected_fund_name = selected_fund_name
                        st.session_state.chat_history = []
                        st.session_state.rag_chain = None
            else:
                st.info(f"No active funds found for {selected_amc}")

        st.divider()

        # ── Database Stats + Data Freshness ──────────────────────────
        st.markdown("### 📈 Database Stats")

        col_s1, col_s2 = st.columns(2)
        with col_s1:
            st.metric("Total Funds", f"{fund_count:,}")
        with col_s2:
            st.metric("AMCs Tracked", f"{len(amcs)}")

        # Data freshness
        try:
            freshness = get_data_freshness()
            enriched = get_enriched_fund_count()

            col_s3, col_s4 = st.columns(2)
            with col_s3:
                st.metric("Enriched", f"{enriched:,}")
            with col_s4:
                st.metric("With Managers", f"{freshness['funds_with_managers']:,}")

            nav_date = freshness.get("latest_nav_date", "Unknown")
            if nav_date and nav_date != "Unknown":
                st.caption(f"📅 NAV Data: {nav_date}")
            else:
                st.caption("📅 NAV Data: Not available")
        except Exception:
            pass

        st.metric("Vector Store", "✅ Ready" if vectorstore_exists else "❌ Not Built")

        st.divider()

        # Sample questions
        st.markdown("### 💡 Sample Questions")
        st.markdown("""
        - What is the NAV?
        - What category is this fund?
        - What are the returns?
        - Who is the fund manager?
        - Which fund house manages this?
        - What type of scheme is this?
        """)

        st.divider()

        # Data management
        with st.expander("🔄 Data Management"):
            st.caption("Quick refresh (NAV + new funds):")
            st.code("python -m scripts.refresh_data", language="bash")

            st.caption("Full refresh (includes fund managers):")
            st.code("python -m scripts.refresh_data --full", language="bash")

            st.caption("Individual steps:")
            st.code("python -m scripts.scrape_nav", language="bash")
            st.code("python -m scripts.scrape_scheme_details --limit 500", language="bash")
            st.code("python -m scripts.scrape_fund_managers --limit 5000", language="bash")
            st.code("python -m scripts.ingest_funds --texts-only", language="bash")


    # ── Main Area ────────────────────────────────────────────────────
    st.markdown("<h1 class='main-header'>🏦 SID Chatbot</h1>", unsafe_allow_html=True)
    st.markdown("<p class='sub-header'>Mutual Fund Intelligence Platform — Ask questions about any fund</p>", unsafe_allow_html=True)

    # ── Fund Info Card ───────────────────────────────────────────────
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
                manager = fund_info.get("fund_manager")
                st.metric("👤 Manager", (manager[:25] + "..." if manager and len(manager) > 25 else manager) or "N/A")

            # Fund name banner
            st.info(f"🏦 **{fund_info.get('scheme_name', 'Unknown')}** | {fund_info.get('fund_house', 'Unknown AMC')} | Code: {fund_info.get('scheme_code', 'N/A')}")

        st.divider()

        # ── Load RAG Chain ───────────────────────────────────────────
        if st.session_state.rag_chain is None and vectorstore_exists:
            with st.spinner("🔄 Loading AI model + vector store..."):
                try:
                    from src.embeddings import load_vectorstore
                    from langchain_core.documents import Document

                    vectorstore = load_vectorstore()

                    # Get all documents from the vectorstore for BM25
                    all_docs_with_scores = vectorstore.similarity_search_with_score("", k=1000)
                    all_docs = [doc for doc, score in all_docs_with_scores]

                    if not all_docs:
                        all_docs = [Document(page_content="placeholder", metadata={"page": 0})]

                    st.session_state.rag_chain = build_rag_chain(vectorstore, all_docs)
                    st.success("✅ AI model loaded and ready!")
                except ValueError as e:
                    # API key issues
                    st.error(f"⚙️ Configuration Error: {e}")
                    st.info("Check your `.env` file and ensure `GROQ_API_KEY` is set correctly.")
                except Exception as e:
                    st.error(f"❌ Error loading model: {e}")
                    st.info("Make sure to run `python -m scripts.ingest_funds` first.")

        elif not vectorstore_exists:
            st.warning("⚠️ Vector store not built yet. Run: `python -m scripts.ingest_funds --texts-only`")

        # ── Chat Interface ───────────────────────────────────────────

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

                        except ValueError as e:
                            # API key / config issues
                            error_msg = f"⚙️ Configuration Error: {str(e)}"
                            st.error(error_msg)
                            st.session_state.chat_history.append({
                                "role": "assistant",
                                "content": error_msg,
                            })

                        except Exception as e:
                            error_str = str(e)
                            if "rate limit" in error_str.lower() or "429" in error_str:
                                error_msg = "⏳ Rate limit reached. The free Groq tier allows 30 requests/minute. Please wait ~30 seconds and try again."
                            elif "timeout" in error_str.lower():
                                error_msg = "⏱️ Request timed out. The server may be busy — please try again."
                            elif "connection" in error_str.lower():
                                error_msg = "🌐 Network error. Please check your internet connection and try again."
                            else:
                                error_msg = f"❌ Error: {error_str}"

                            st.error(error_msg)
                            st.session_state.chat_history.append({
                                "role": "assistant",
                                "content": error_msg,
                            })

    else:
        st.info("👈 Select a fund from the sidebar to start asking questions.")
        st.markdown("""
        **How to use:**
        1. **Quick Search**: Type any fund name in the search box (e.g., "HDFC Flexi Cap")
        2. **Browse**: Select an AMC, then pick a fund from the dropdown
        3. **Ask**: Type your question in the chat box below
        """)


# ══════════════════════════════════════════════════════════════════════
#                          ROUTING (Login vs App)
# ══════════════════════════════════════════════════════════════════════

if st.session_state.authenticated:
    show_main_app()
else:
    show_login_page()
