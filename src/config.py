"""
config.py — Centralized configuration for the SID Chatbot.

All settings in one place so you never have to hunt for magic numbers.
"""

import os
from dotenv import load_dotenv

# Load API keys from .env file
load_dotenv()

# ── Google Gemini (FREE) ──────────────────────────────────────────────
# Get your FREE key from: https://aistudio.google.com/apikey
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
LLM_MODEL = "gemini-2.0-flash"             # Latest Gemini 2.0 model
LLM_TEMPERATURE = 0.1                      # Low = more factual, less creative

# ── Embedding Model ───────────────────────────────────────────────────
# Local model (runs on your laptop, no API needed, no rate limits)
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# ── Chunking ──────────────────────────────────────────────────────────
CHUNK_SIZE = 1000          # characters per chunk (~250 tokens)
CHUNK_OVERLAP = 200        # overlap between chunks to preserve context

# ── Vector Database ───────────────────────────────────────────────────
VECTORSTORE_DIR = "vectorstore"        # FAISS index storage folder

# ── Retrieval ─────────────────────────────────────────────────────────
TOP_K = 5                  # Number of chunks to retrieve per query

# ── Paths ─────────────────────────────────────────────────────────────
DATA_DIR = "data/sample"
