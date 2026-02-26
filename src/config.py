"""
config.py — Centralized configuration for the SID Chatbot.

All settings in one place so you never have to hunt for magic numbers.
"""

import os
from dotenv import load_dotenv

# Load API keys from .env file
load_dotenv()

# ── Google Gemini ─────────────────────────────────────────────────────
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

# ── Groq (FREE, ultra-fast cloud inference) ───────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
LLM_MODEL = "llama-3.3-70b-versatile"      # Fast 70B model on Groq
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
SIDS_DIR = "data/sids"                 # Directory for manually placed SID PDFs
DATABASE_PATH = "data/funds.db"        # SQLite database for fund metadata

# ── External APIs ─────────────────────────────────────────────────────
AMFI_NAV_URL = "https://www.amfiindia.com/spages/NAVAll.txt"
MFAPI_BASE_URL = "https://api.mfapi.in/mf"

# ── Top AMCs to track ─────────────────────────────────────────────────
# These AMC names are used to filter relevant schemes from AMFI data.
# They must match the fund house names used by AMFI (as they appear in NAVAll.txt).
TOP_AMCS = [
    # Tier 1
    "SBI Mutual Fund",
    "ICICI Prudential Mutual Fund",
    "HDFC Mutual Fund",
    "Nippon India Mutual Fund",
    "Kotak Mahindra Mutual Fund",
    "Aditya Birla Sun Life Mutual Fund",
    "UTI Mutual Fund",
    "Axis Mutual Fund",
    "Mirae Asset Mutual Fund",
    "DSP Mutual Fund",
    # Tier 2
    "Franklin Templeton Mutual Fund",
    "Tata Mutual Fund",
    "Bandhan Mutual Fund",
    "Motilal Oswal Mutual Fund",
    "Edelweiss Mutual Fund",
    "Canara Robeco Mutual Fund",
    "HSBC Mutual Fund",
    "Baroda BNP Paribas Mutual Fund",
    "LIC Mutual Fund",
    # Tier 3
    "360 ONE Mutual Fund",
    "Bajaj Finserv Mutual Fund",
    "Navi Mutual Fund",
    "Quant Mutual Fund",
    "PPFAS Mutual Fund",
    "JM Financial Mutual Fund",
    "Union Mutual Fund",
    "Sundaram Mutual Fund",
    "Mahindra Manulife Mutual Fund",
    "IIFL Mutual Fund",
    # Tier 4
    "WhiteOak Capital Mutual Fund",
    "Trust Mutual Fund",
    "Invesco Mutual Fund",
    "PGIM India Mutual Fund",
    "Shriram Mutual Fund",
    "Groww Mutual Fund",
    "Helios Mutual Fund",
]
