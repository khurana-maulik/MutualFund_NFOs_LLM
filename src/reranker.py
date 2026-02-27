"""
reranker.py — Re-rank retrieved chunks using a cross-encoder.

WHY RE-RANKING?
  - Initial retrieval (BM25 + FAISS) casts a wide net (top-10 chunks)
  - Re-ranker scores each chunk against the EXACT question
  - Returns only the top-K most relevant chunks

EXAMPLE:
  Question: "What is the fund manager's experience?"
  
  Initial retrieval might return:
    1. Chunk about fund manager name (good!)
    2. Chunk about fund manager fees (somewhat relevant)
    3. Chunk about management structure (generic)
    ...
  
  Re-ranker scores:
    1. High score (0.92) — directly answers experience
    2. Low score (0.34) — talks about fees, not experience
    3. Very low score (0.15) — generic org structure
  
  Final output: Only chunk #1 makes it to the LLM!

HOW IT WORKS:
  - Cross-encoder: Scores (question, chunk) pairs
  - Much more accurate than bi-encoders (FAISS)
  - But slower, so we only use it on top-K candidates

MODEL:
  - `cross-encoder/ms-marco-MiniLM-L-6-v2`
  - Trained on MS MARCO dataset (question-passage pairs)
  - Fast: ~50ms per chunk on CPU
  - Size: ~80MB download (cached after first run)
"""

from typing import List, Tuple
from sentence_transformers import CrossEncoder
from langchain_core.documents import Document


class Reranker:
    """
    Re-rank retrieved chunks using a cross-encoder model.
    """
    
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        """
        Initialize the re-ranker.
        
        Args:
            model_name: HuggingFace cross-encoder model name
        """
        print("[LOAD] Loading re-ranker model (first time downloads ~80MB)...")
        self.model = CrossEncoder(model_name)
        print("   [OK] Re-ranker ready!")
    
    def rerank(
        self,
        question: str,
        documents: List[Document],
        top_k: int = 5,
    ) -> Tuple[List[Document], List[float]]:
        """
        Re-rank documents based on relevance to the question.
        
        Args:
            question: User question
            documents: List of retrieved documents
            top_k: Number of top documents to return
        
        Returns:
            Tuple of:
              - List of re-ranked documents (top-K)
              - List of re-ranker scores (0-1 scale, higher = more relevant)
        """
        if not documents:
            return [], []
        
        # Create (question, chunk) pairs for the cross-encoder
        pairs = [(question, doc.page_content) for doc in documents]
        
        # Get scores from cross-encoder
        scores = self.model.predict(pairs)
        
        # Sort by score (descending)
        doc_score_pairs = list(zip(documents, scores))
        doc_score_pairs.sort(key=lambda x: x[1], reverse=True)
        
        # Return top-K
        top_docs = [doc for doc, _ in doc_score_pairs[:top_k]]
        top_scores = [float(score) for _, score in doc_score_pairs[:top_k]]
        
        return top_docs, top_scores


def create_reranker() -> Reranker:
    """
    Factory function to create a re-ranker instance.
    """
    return Reranker()
