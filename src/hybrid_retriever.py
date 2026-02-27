"""
hybrid_retriever.py — Combine keyword search (BM25) + semantic search (FAISS).

WHY HYBRID?
  - Semantic search: "exit load" → finds "redemption charges" (concept match)
  - BM25 search: "exit load" → finds exact phrase "exit load" (keyword match)
  - Combined: Best of both worlds!

EXAMPLE:
  Question: "What is the NAV calculation method?"
  - FAISS alone might return chunks about "valuation" or "pricing"
  - BM25 ensures chunks with exact phrase "NAV calculation" rank high
  - Hybrid: Merges both, gets the most relevant chunks

ALGORITHM:
  1. Run BM25 retrieval → top 10 chunks with keyword scores
  2. Run FAISS retrieval → top 10 chunks with semantic scores
  3. Normalize both scores to [0, 1]
  4. Weighted average: 0.5 * BM25 + 0.5 * FAISS (configurable)
  5. Deduplicate and return top-K
"""

from typing import List
from rank_bm25 import BM25Okapi
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document


class HybridRetriever:
    """
    Combines BM25 (keyword) and FAISS (semantic) retrieval.
    """
    
    def __init__(
        self,
        vectorstore: FAISS,
        documents: List[Document],
        k: int = 5,
        bm25_weight: float = 0.5,
        semantic_weight: float = 0.5,
    ):
        """
        Initialize hybrid retriever.
        
        Args:
            vectorstore: FAISS vector store
            documents: All document chunks (for BM25 indexing)
            k: Number of chunks to return
            bm25_weight: Weight for BM25 scores (0-1)
            semantic_weight: Weight for FAISS scores (0-1)
        """
        self.vectorstore = vectorstore
        self.documents = documents
        self.k = k
        self.bm25_weight = bm25_weight
        self.semantic_weight = semantic_weight
        
        # Build BM25 index
        tokenized_docs = [doc.page_content.lower().split() for doc in documents]
        self.bm25 = BM25Okapi(tokenized_docs)
        
        print(f"   [OK] Hybrid retriever ready (BM25: {bm25_weight}, Semantic: {semantic_weight})")
    
    def retrieve(self, query: str, k: int = None) -> List[Document]:
        """
        Retrieve top-K chunks using hybrid search.
        
        Args:
            query: User question
            k: Number of chunks to return (overrides default)
        
        Returns:
            List of Document objects sorted by hybrid score
        """
        k = k or self.k
        
        # Step 1: BM25 retrieval
        tokenized_query = query.lower().split()
        bm25_scores = self.bm25.get_scores(tokenized_query)
        
        # Normalize BM25 scores to [0, 1]
        max_bm25 = max(bm25_scores) if max(bm25_scores) > 0 else 1
        bm25_scores_norm = [score / max_bm25 for score in bm25_scores]
        
        # Step 2: FAISS retrieval (get 2*k to have more candidates)
        semantic_docs = self.vectorstore.similarity_search_with_score(query, k=k*2)
        
        # Build a score map: {doc_index: semantic_score}
        semantic_scores = {}
        for doc, score in semantic_docs:
            # FAISS returns distance (lower = better), convert to similarity
            similarity = 1 / (1 + score)  # Normalize to [0, 1]
            
            # Find index of this doc in self.documents
            for idx, original_doc in enumerate(self.documents):
                if original_doc.page_content == doc.page_content:
                    semantic_scores[idx] = similarity
                    break
        
        # Normalize semantic scores
        max_semantic = max(semantic_scores.values()) if semantic_scores else 1
        semantic_scores_norm = {idx: score / max_semantic for idx, score in semantic_scores.items()}
        
        # Step 3: Compute hybrid scores
        hybrid_scores = []
        for idx, doc in enumerate(self.documents):
            bm25_score = bm25_scores_norm[idx] if idx < len(bm25_scores_norm) else 0
            semantic_score = semantic_scores_norm.get(idx, 0)
            
            # Weighted combination
            hybrid_score = (
                self.bm25_weight * bm25_score +
                self.semantic_weight * semantic_score
            )
            
            hybrid_scores.append((idx, hybrid_score, doc))
        
        # Step 4: Sort by hybrid score and return top-K
        hybrid_scores.sort(key=lambda x: x[1], reverse=True)
        top_docs = [doc for _, _, doc in hybrid_scores[:k]]
        
        return top_docs


def create_hybrid_retriever(
    vectorstore: FAISS,
    documents: List[Document],
    k: int = 5,
) -> HybridRetriever:
    """
    Factory function to create a hybrid retriever.
    
    Args:
        vectorstore: FAISS vector store
        documents: All document chunks
        k: Number of chunks to return
    
    Returns:
        Configured HybridRetriever instance
    """
    return HybridRetriever(
        vectorstore=vectorstore,
        documents=documents,
        k=k,
        bm25_weight=0.5,  # 50% keyword matching
        semantic_weight=0.5,  # 50% semantic similarity
    )
