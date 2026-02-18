"""
embeddings.py — Create vector embeddings and store them in FAISS.

HOW IT WORKS:
  1. Load Google's free embedding model (same API key as Gemini, no extra cost)
  2. Convert text chunks into numerical vectors (embeddings)
  3. Store embeddings in FAISS (a local vector database by Meta/Facebook)
  4. Save FAISS index to disk (survives app restarts)
  5. When user asks a question, we search FAISS for the most similar chunks

WHY FAISS?
  - Free and open source (by Meta AI)
  - Blazing fast similarity search
  - Runs locally (no cloud needed)
  - Saves to disk (persists between restarts)
  - No pydantic v1 dependency (works with Python 3.14)
"""

import os
import shutil
from sentence_transformers import SentenceTransformer
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_community.embeddings import HuggingFaceEmbeddings
from src.config import EMBEDDING_MODEL, VECTORSTORE_DIR


def get_embedding_model() -> HuggingFaceEmbeddings:
    """
    Load a local embedding model (runs on your laptop, no API needed).
    
    Model: all-MiniLM-L6-v2
      - FREE: No API costs ever
      - Fast: Runs on CPU
      - Quality: Good for document retrieval
      - Size: Downloads once (~80MB), cached after that
      - Output: 384-dimensional vectors
    """
    print("🧠 Loading local embedding model (first time downloads ~80MB)...")
    
    embeddings = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )
    
    print("   ✅ Embedding model ready!")
    return embeddings


def create_vectorstore(chunks: list[Document]) -> tuple[FAISS, list[Document]]:
    """
    Create a FAISS vector store from document chunks.
    
    What happens:
      1. Each chunk's text is embedded using local HuggingFace model
      2. Returns a 384-dim vector for each chunk
      3. FAISS indexes all vectors for fast similarity search
      4. Index is saved to disk (vectorstore/ folder)
    
    Args:
        chunks: List of LangChain Documents from the chunker
    
    Returns:
        Tuple of (FAISS vectorstore, list of chunks)
        The chunks are returned for BM25 indexing in hybrid retrieval
    """
    # Clear old data if exists (fresh start for each PDF upload)
    if os.path.exists(VECTORSTORE_DIR):
        shutil.rmtree(VECTORSTORE_DIR)
    
    embeddings = get_embedding_model()
    
    print(f"📦 Creating vector store with {len(chunks)} chunks...")
    
    vectorstore = FAISS.from_documents(
        documents=chunks,
        embedding=embeddings,
    )
    
    # Save to disk so it persists between app restarts
    vectorstore.save_local(VECTORSTORE_DIR)
    
    print(f"   ✅ Vector store created and saved to '{VECTORSTORE_DIR}/'")
    return vectorstore, chunks


def load_vectorstore() -> FAISS:
    """
    Load an existing vector store from disk.
    
    Use this when the app restarts and you don't want to re-process the PDF.
    """
    embeddings = get_embedding_model()
    
    vectorstore = FAISS.load_local(
        VECTORSTORE_DIR,
        embeddings,
        allow_dangerous_deserialization=True,  # Required for loading from disk
    )
    
    return vectorstore
