# 🏦 SID Chatbot — Mutual Fund Intelligence Platform

[![Python](https://img.shields.io/badge/Python-3.13%2B-blue.svg)](https://www.python.org/)
[![LangChain](https://img.shields.io/badge/LangChain-Latest-green.svg)](https://www.langchain.com/)
[![Groq](https://img.shields.io/badge/LLM-Groq%20Llama%203.3%2070B-orange.svg)](https://groq.com/)
[![AMFI](https://img.shields.io/badge/Data-AMFI%20India-purple.svg)](https://amfiindia.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> AI-powered mutual fund analysis platform that scrapes data from **14,000+ Indian mutual funds**, builds a searchable knowledge base, and lets you chat with fund data using RAG (Retrieval-Augmented Generation).

---

## 🎯 What It Does

Instead of manually reading 100+ page SID documents, this platform:

1. **Scrapes** daily NAV data for **14,287 schemes** from AMFI India
2. **Enriches** each fund with returns, category, and metadata via mfapi.in
3. **Indexes** everything in a FAISS vector store for instant semantic search
4. **Answers** your questions using Groq's ultra-fast Llama 3.3 70B model
5. **Shows** confidence scores, source citations, and fund info at a glance

**Time saved:** From hours of reading PDFs → instant answers ⚡

---

## 🏗️ Architecture

```
                          ┌─────────────────────────────────────┐
                          │        DATA INGESTION PIPELINE       │
                          │                                     │
 AMFI NAVAll.txt ────────►│  scrape_nav.py      ────► SQLite   │
 (14,287 funds)           │                           (funds.db)│
                          │                                     │
 mfapi.in API ───────────►│  scrape_scheme_details.py           │
 (returns + metadata)     │       │                             │
                          │       ▼                             │
                          │  Text Documents (data/fund_texts/)  │
                          │       │                             │
                          │       ▼                             │
                          │  ingest_funds.py  ────► FAISS Index │
                          └─────────────────────────────────────┘
                                        │
                                        ▼
                          ┌─────────────────────────────────────┐
                          │          STREAMLIT APP (app.py)      │
                          │                                     │
                          │  AMC Dropdown ──► Fund Selector     │
                          │       │                             │
                          │       ▼                             │
                          │  Fund Info Card (NAV, category...)  │
                          │       │                             │
                          │       ▼                             │
                          │  User Question                      │
                          │       │                             │
                          │       ▼                             │
                          │  Hybrid Search (BM25 + FAISS)       │
                          │       │                             │
                          │       ▼                             │
                          │  Re-Rank (Cross-Encoder)            │
                          │       │                             │
                          │       ▼                             │
                          │  Groq (Llama 3.3 70B) ──► Answer   │
                          │       + Citations + Confidence      │
                          └─────────────────────────────────────┘
```

### Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------| 
| **Frontend** | Streamlit | Fund selector + chat UI |
| **Database** | SQLite | Structured fund metadata (14K+ schemes) |
| **LLM** | Groq + Llama 3.3 70B | Ultra-fast cloud inference |
| **Embeddings** | `all-MiniLM-L6-v2` (local) | 384-dim semantic vectors |
| **Vector DB** | FAISS (Meta AI) | Fast similarity search |
| **Retrieval** | BM25 + FAISS hybrid | Keyword + semantic matching |
| **Re-ranking** | `ms-marco-MiniLM-L-6-v2` | Cross-encoder precision |
| **Data Source** | AMFI India + mfapi.in | NAV, returns, scheme details |
| **PDF Parsing** | PyMuPDF + pdfplumber | Optional SID PDF ingestion |

---

## 📊 Data Coverage

| Metric | Value |
|--------|-------|
| **Total Schemes in DB** | 14,287 |
| **Enriched with Returns** | 5,500+ |
| **AMCs Tracked** | 37 (all major Indian fund houses) |
| **Data Points per Fund** | NAV, 1M/3M/6M/1Y/3Y/5Y returns, category, type |
| **Data Source** | AMFI India (official) + mfapi.in (free API) |
| **Update Frequency** | On-demand (run scraper anytime) |

### AMCs Covered (Top Tier)

SBI · ICICI Prudential · HDFC · Nippon India · Kotak Mahindra · Aditya Birla Sun Life · UTI · Axis · Mirae Asset · DSP · Franklin Templeton · Tata · Bandhan · Motilal Oswal · Edelweiss · Canara Robeco · HSBC · Baroda BNP Paribas · LIC · Quant · PPFAS · Sundaram · Bajaj Finserv · and more...

---

## 🚀 Quick Start

### Prerequisites
- Python 3.13+
- 4GB RAM minimum
- Internet connection (for Groq API + initial data scraping)

### Installation

```bash
# 1. Clone repository
git clone https://github.com/yourusername/sid-chatbot.git
cd sid-chatbot

# 2. Create virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/Mac

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up API key
# Create .env file with your Groq API key (free at https://console.groq.com)
echo "GROQ_API_KEY=your_key_here" > .env
```

### Data Setup (One-Time)

```bash
# On Windows, set encoding first:
$env:PYTHONIOENCODING='utf-8'

# Step 1: Scrape all NAV data from AMFI (~14K funds, takes ~2 seconds)
python -m scripts.scrape_nav

# Step 2: Enrich funds with returns data (adjust limit as needed)
python -m scripts.scrape_scheme_details --limit 5000 --delay 0.3

# Step 3: Build the FAISS vector store
python -m scripts.ingest_funds --texts-only
```

### Launch

```bash
streamlit run app.py
```

Open **http://localhost:8501** → Select an AMC → Pick a fund → Ask questions!

---

## 💡 Usage

### Asking Questions

Select a fund from the sidebar, then ask:

| Question | What You Get |
|----------|-------------|
| "What is the NAV?" | Current NAV with date |
| "What are the returns?" | 1M, 3M, 6M, 1Y, 3Y, 5Y returns |
| "What category is this fund?" | Scheme category and type |
| "Compare the performance" | Returns data with confidence scoring |

### Fund Info Card

Every selected fund shows a live info card with:
- 💰 **Current NAV** with date
- 📂 **Category** (Equity, Debt, Hybrid, etc.)
- 📊 **Scheme Type** (Open/Close ended)
- 🏦 **AMC Name** and scheme code

### Confidence Scoring

Every answer includes a confidence level:
- 🟢 **HIGH** (≥0.7) — Strong match, reliable answer
- 🟡 **MEDIUM** (0.4–0.7) — Moderate relevance
- 🔴 **LOW** (<0.4) — Weak match or uncertain

---

## 🎓 Technical Deep Dive

### 1. Data Pipeline

```
AMFI NAVAll.txt ──parse──► SQLite (14K+ schemes)
                              │
mfapi.in/{code} ──enrich──► fund_texts/*.txt (with returns)
                              │
                     chunk + embed
                              │
                              ▼
                        FAISS Index (vectorstore/)
```

**NAV Parser:** Reads AMFI's semicolon-delimited text file, extracts scheme code, ISIN, name, NAV, date, fund house, and category for every active scheme.

**Enricher:** Calls mfapi.in for each scheme, calculates returns from NAV history (1M, 3M, 6M, 1Y, 3Y, 5Y CAGR), and saves structured text documents.

**Ingestion:** Chunks text documents using `RecursiveCharacterTextSplitter`, embeds with `all-MiniLM-L6-v2`, and stores in FAISS with fund metadata.

### 2. Hybrid Search

Combines two retrieval methods for maximum accuracy:

| Method | Strength | Example |
|--------|----------|---------|
| **BM25** (keyword) | Exact phrases | "exit load" → finds "exit load" |
| **FAISS** (semantic) | Concept matching | "exit load" → finds "redemption charges" |

Merged with equal weights: `0.5 × BM25 + 0.5 × FAISS`

### 3. Re-Ranking

After hybrid retrieval returns 10 candidates, a **cross-encoder** (`ms-marco-MiniLM-L-6-v2`) scores each (question, chunk) pair jointly, keeping the top 5 most relevant chunks for the LLM.

### 4. Prompt Engineering

Financial domain-specific prompt with strict guardrails:
- ✅ Answer ONLY from provided context
- ✅ Cite page/source references
- ✅ Explain financial terms simply
- ❌ NEVER give investment advice
- ❌ NEVER use general knowledge

---

## 📁 Project Structure

```
sid-chatbot/
├── app.py                          # Streamlit frontend (fund selector + chat)
├── src/
│   ├── config.py                   # All config: API keys, models, AMC list
│   ├── database.py                 # SQLite database schema + query helpers
│   ├── pdf_parser.py               # PDF parsing (PyMuPDF + pdfplumber)
│   ├── chunker.py                  # Text chunking strategy
│   ├── embeddings.py               # Vector embeddings + FAISS operations
│   ├── hybrid_retriever.py         # BM25 + FAISS hybrid search
│   ├── reranker.py                 # Cross-encoder re-ranking
│   └── rag_chain.py                # RAG pipeline (Groq + Llama 3.3 70B)
├── scripts/
│   ├── scrape_nav.py               # Fetch NAV data from AMFI (14K+ funds)
│   ├── scrape_scheme_details.py    # Enrich funds via mfapi.in API
│   └── ingest_funds.py             # Build FAISS vector store
├── data/
│   ├── funds.db                    # SQLite database (auto-created)
│   ├── fund_texts/                 # Enriched fund text files (auto-created)
│   ├── sids/                       # Optional: manually placed SID PDFs
│   └── sample/                     # Sample SID PDFs
├── vectorstore/                    # FAISS index (auto-created)
├── evaluation/
│   └── test_questions.json         # Test dataset
├── requirements.txt                # Python dependencies
├── .env                            # API keys (not committed)
├── Dockerfile                      # Docker container config
├── docker-compose.yml              # Docker compose setup
└── README.md                       # This file
```

---

## 🧪 Testing

### Quick Test

```bash
# Verify data pipeline
python -m scripts.scrape_nav                                    # Should show 14K+ funds
python -m scripts.scrape_scheme_details --limit 10 --delay 0.3  # Should enrich 10
python -m scripts.ingest_funds --texts-only                     # Should build FAISS
```

### Sample Questions

| Question | Expected Confidence | Tests |
|----------|-------------------|-------|
| "What is the NAV?" | 🟢 HIGH | Direct data match |
| "What are the 1-year returns?" | 🟢 HIGH | Calculated returns |
| "What category is this fund?" | 🟢 HIGH | Metadata retrieval |
| "Who is the fund manager?" | 🟡 MEDIUM | May not be in scraped data |
| "Compare with XYZ fund" | 🔴 LOW | Cross-fund query |

---

## 🛠️ Configuration

All settings in `src/config.py`:

```python
# LLM
LLM_MODEL = "llama-3.3-70b-versatile"   # Groq model
LLM_TEMPERATURE = 0.1                    # Low = more factual

# Embeddings
EMBEDDING_MODEL = "all-MiniLM-L6-v2"     # Local, no API needed

# Retrieval
TOP_K = 5                                # Chunks per query
CHUNK_SIZE = 1000                        # Characters per chunk
CHUNK_OVERLAP = 200                      # Overlap between chunks

# Data
AMFI_NAV_URL = "https://www.amfiindia.com/spages/NAVAll.txt"
MFAPI_BASE_URL = "https://api.mfapi.in/mf"
```

### Switching LLM Providers

The project supports multiple LLM providers. Update `rag_chain.py`:

| Provider | Model | Pros |
|----------|-------|------|
| **Groq** (current) | Llama 3.3 70B | Free, ultra-fast |
| **Google Gemini** | gemini-2.0-flash | Free tier, multimodal |
| **Ollama** | qwen2.5 | 100% local, private |

---

## 🎯 Future Enhancements

- [ ] **Multi-fund comparison** — Compare returns across funds side-by-side
- [ ] **Automated fund report card** — One-page summary per fund
- [ ] **NFO monitoring** — Auto-detect and ingest new fund offers
- [ ] **SID PDF auto-download** — Selenium-based scraper for AMC websites
- [ ] **RAGAS evaluation** — Automated accuracy measurement
- [ ] **Export summaries** — PDF/DOCX report generation
- [ ] **Caching** — Store repeat queries for instant answers

---

## 📜 License

MIT License — Free to use and modify

---

## 📧 Contact

**Maulik** — AI/ML Engineer  
[GitHub](https://github.com/yourusername) | [LinkedIn](https://linkedin.com/in/yourprofile)

---

## 🙏 Acknowledgments

- **AMFI India** — Official NAV data source
- **mfapi.in** — Free mutual fund API
- **Groq** — Ultra-fast LLM inference
- **LangChain** — RAG framework
- **Meta AI** — FAISS vector search
- **HuggingFace** — Embedding & re-ranking models
- **Streamlit** — Frontend framework

---

**Built with ❤️ for investors seeking clarity in complex financial documents**
