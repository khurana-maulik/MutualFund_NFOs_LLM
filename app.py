"""
SID Chatbot — Streamlit Frontend
=================================
A clean, interactive UI for asking questions about mutual fund SIDs.

Run with:  streamlit run app.py
"""

import streamlit as st
import tempfile
import os

from src.pdf_parser import parse_pdf
from src.chunker import create_chunks
from src.embeddings import create_vectorstore
from src.rag_chain import build_rag_chain, ask_question


# ── Page Configuration ────────────────────────────────────────────────
st.set_page_config(
    page_title="SID Chatbot — Mutual Fund Document Analyst",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS for better styling ─────────────────────────────────────
st.markdown("""
<style>
    /* Main header */
    .main-header {
        text-align: center;
        padding: 1rem 0;
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
    
    /* Status indicator */
    .status-ready {
        color: #4CAF50;
        font-weight: bold;
    }
    .status-loading {
        color: #FF9800;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)


# ── Session State Initialization ──────────────────────────────────────
# Streamlit reruns the script on every interaction.
# Session state preserves data between reruns.

if "rag_chain" not in st.session_state:
    st.session_state.rag_chain = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "document_loaded" not in st.session_state:
    st.session_state.document_loaded = False
if "doc_name" not in st.session_state:
    st.session_state.doc_name = ""


# ── Sidebar: Document Upload ─────────────────────────────────────────
with st.sidebar:
    st.header("📄 Upload SID Document")
    st.caption("Upload a mutual fund Scheme Information Document (PDF)")
    
    uploaded_file = st.file_uploader(
        "Choose a SID PDF",
        type=["pdf"],
        help="Upload the SID PDF from any AMC like HDFC, SBI, ICICI, Axis, etc."
    )
    
    if uploaded_file is not None:
        # Only process if it's a new file
        if uploaded_file.name != st.session_state.doc_name:
            with st.spinner("🔄 Processing document... This may take 1-2 minutes on first run."):
                
                # Save uploaded file to a temp location
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    tmp.write(uploaded_file.getvalue())
                    tmp_path = tmp.name
                
                try:
                    # Step 1: Parse PDF
                    st.info("📄 Step 1/4: Parsing PDF...")
                    parsed_pages = parse_pdf(tmp_path)
                    
                    # Step 2: Create chunks
                    st.info("✂️ Step 2/4: Chunking text...")
                    chunks = create_chunks(parsed_pages, uploaded_file.name)
                    
                    # Step 3: Create embeddings & vector store
                    st.info("🧠 Step 3/4: Creating embeddings...")
                    vectorstore, chunks = create_vectorstore(chunks)
                    
                    # Step 4: Build RAG chain (with hybrid retrieval)
                    st.info("🔗 Step 4/4: Building RAG chain...")
                    st.session_state.rag_chain = build_rag_chain(vectorstore, chunks)
                    st.session_state.document_loaded = True
                    st.session_state.doc_name = uploaded_file.name
                    st.session_state.chat_history = []  # Reset chat for new doc
                    
                    st.success(f"✅ Ready! Loaded: {uploaded_file.name}")
                    st.info(f"📊 Stats: {len(parsed_pages)} pages → {len(chunks)} chunks")
                    
                except Exception as e:
                    st.error(f"❌ Error processing PDF: {str(e)}")
                
                finally:
                    # Clean up temp file
                    os.unlink(tmp_path)
        else:
            st.success(f"✅ Document loaded: {uploaded_file.name}")
    
    st.divider()
    
    # Quick info
    st.markdown("### 💡 Sample Questions")
    st.markdown("""
    - What is the investment objective?
    - What is the exit load?
    - What are the risk factors?
    - What is the expense ratio?
    - Who is the fund manager?
    - What is the benchmark index?
    - What is the minimum investment amount?
    """)
    
    st.divider()
    st.caption("🔒 Your document is processed locally. No data is stored permanently.")


# ── Main Area: Chat Interface ─────────────────────────────────────────

st.markdown("<h1 class='main-header'>🏦 SID Chatbot</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: gray;'>Ask questions about any Mutual Fund Scheme Information Document</p>", unsafe_allow_html=True)

# Show status
if not st.session_state.document_loaded:
    st.info("👈 Upload a SID PDF from the sidebar to get started.")
    st.stop()

# Display chat history
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        
        # Show sources for assistant messages
        if message["role"] == "assistant" and "sources" in message:
            with st.expander("📚 View Source Citations", expanded=False):
                for i, source in enumerate(message["sources"], 1):
                    st.markdown(
                        f"**Source {i}** — Page {source['page']} ({source['type']})"
                    )
                    st.text(source["text"][:300] + "...")
                    st.divider()

# Chat input
user_question = st.chat_input("Ask a question about the SID...")

if user_question:
    # Display user message
    with st.chat_message("user"):
        st.markdown(user_question)
    
    # Add to history
    st.session_state.chat_history.append({
        "role": "user",
        "content": user_question,
    })
    
    # Get answer from RAG chain
    with st.chat_message("assistant"):
        with st.spinner("🤔 Searching document and generating answer..."):
            try:
                result = ask_question(st.session_state.rag_chain, user_question)
                
                # Display confidence badge
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
                
                # Add to history
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
