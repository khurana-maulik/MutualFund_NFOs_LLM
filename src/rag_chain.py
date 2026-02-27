"""
rag_chain.py — The brain of the chatbot: Retrieval-Augmented Generation.

HOW RAG WORKS (simple explanation):
  1. User asks a question
  2. We search the FAISS vector database for the 5 most relevant chunks
  3. We format the chunks + question into a prompt
  4. Groq (cloud LLM) generates an answer using ONLY the provided chunks
  5. We return the answer + source citations

Uses Groq API with Llama 3.3 70B (ultra-fast, free tier).
Includes rate limiting with exponential backoff for Groq free tier (30 RPM).
"""

import time
from langchain_groq import ChatGroq
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import PromptTemplate
from src.config import TOP_K, LLM_MODEL, LLM_TEMPERATURE, GROQ_API_KEY


# ── System Prompt ─────────────────────────────────────────────────────
# This is what makes our chatbot DIFFERENT from a generic PDF chatbot.

SYSTEM_PROMPT = """You are an expert financial document analyst specializing in Indian mutual fund Scheme Information Documents (SIDs). Your job is to help investors understand the SID clearly and accurately.

STRICT RULES:
1. Answer ONLY based on the provided context below. Do NOT use your general knowledge.
2. If the answer is not in the context, say: "I could not find this information in the document."
3. ALWAYS cite the page number(s) where you found the information, like: (Page 5)
4. Explain financial terms in simple language that a beginner investor can understand.
5. NEVER give investment advice like "you should invest" or "this is a good fund".
6. If asked for investment advice, respond: "I can only explain the document. For investment advice, please consult a SEBI-registered financial advisor."
7. For numerical data (expense ratios, loads, allocation %), quote the exact numbers from the document.
8. If the question is about comparing with other funds not in the document, say so clearly.

CONTEXT FROM THE DOCUMENT:
{context}

QUESTION: {question}

ANSWER (with page citations):"""


def validate_api_keys():
    """Check that required API keys are configured."""
    if not GROQ_API_KEY or GROQ_API_KEY == "your_key_here":
        raise ValueError(
            "GROQ_API_KEY not set. Get a free key at https://console.groq.com/keys "
            "and add it to your .env file."
        )


def get_llm():
    """
    Initialize Groq LLM (ultra-fast cloud inference).
    
    Why Groq?
      - Blazing fast: Custom LPU chips, sub-second responses
      - Free tier: 30 RPM, 14.4K tokens/min
      - No local setup: Cloud-based
      - Top models: Llama 3.3 70B, Mixtral, etc.
    """
    validate_api_keys()
    llm = ChatGroq(
        model=LLM_MODEL,
        temperature=LLM_TEMPERATURE,
        groq_api_key=GROQ_API_KEY,
    )
    return llm


def invoke_with_retry(llm, prompt: str, max_retries: int = 3) -> str:
    """
    Invoke LLM with exponential backoff for rate limiting.
    
    Groq free tier: 30 requests/min, 14.4K tokens/min.
    On 429 (rate limit), waits 2s, 4s, 8s before retrying.
    """
    for attempt in range(max_retries):
        try:
            response = llm.invoke(prompt)
            return response
        except Exception as e:
            error_str = str(e).lower()
            if "429" in str(e) or "rate_limit" in error_str or "rate limit" in error_str:
                wait_time = 2 ** (attempt + 1)  # 2, 4, 8 seconds
                print(f"   Rate limited, waiting {wait_time}s (attempt {attempt + 1}/{max_retries})...")
                time.sleep(wait_time)
            elif "authentication" in error_str or "api_key" in error_str or "401" in str(e):
                raise ValueError(
                    "Invalid GROQ_API_KEY. Please check your API key at "
                    "https://console.groq.com/keys and update .env"
                ) from e
            else:
                raise  # Unknown error, don't retry
    raise Exception(
        "Groq API rate limit exceeded. The free tier allows 30 requests/minute. "
        "Please wait a moment and try again."
    )


class RAGChain:
    """
    RAG pipeline with hybrid retrieval (BM25 + semantic).
    
    Flow: Hybrid Retriever → Prompt → Ollama → Answer + Citations
    """
    
    def __init__(self, vectorstore: FAISS, documents: list):
        """
        Initialize RAG chain with hybrid retrieval + re-ranking.
        
        Args:
            vectorstore: FAISS vector store
            documents: All document chunks (for BM25 indexing)
        """
        # Import here to avoid circular imports
        from src.hybrid_retriever import create_hybrid_retriever
        from src.reranker import create_reranker
        
        # Retrieve 10 candidates, then re-rank to get best 5
        self.retriever = create_hybrid_retriever(
            vectorstore=vectorstore,
            documents=documents,
            k=10,  # Retrieve more for re-ranking
        )
        self.reranker = create_reranker()
        self.llm = get_llm()
        self.prompt = PromptTemplate(
            template=SYSTEM_PROMPT,
            input_variables=["context", "question"],
        )
        self.reranker_scores = []  # Store scores for confidence calculation
        print("   [OK] RAG chain ready with hybrid retrieval + re-ranking!")
    
    def ask(self, question: str) -> dict:
        """
        Ask a question and get an answer with sources.
        
        Steps:
          1. Hybrid retrieval: Get top-10 candidates
          2. Re-ranking: Score each chunk, keep best 5
          3. Format them into the prompt
          4. Send to Ollama for answer generation
          5. Return answer + source metadata + confidence
        """
        # Step 1: Hybrid retrieval (top-10 candidates)
        candidate_docs = self.retriever.retrieve(question, k=10)
        
        # Step 2: Re-rank to get top-5 most relevant
        docs, scores = self.reranker.rerank(question, candidate_docs, top_k=TOP_K)
        self.reranker_scores = scores  # Store for confidence calculation
        
        # Step 3: Format context from re-ranked chunks
        context_parts = []
        for doc in docs:
            page = doc.metadata.get("page", "?")
            context_parts.append(f"[Page {page}]: {doc.page_content}")
        
        context = "\n\n---\n\n".join(context_parts)
        
        # Step 4: Format the prompt
        formatted_prompt = self.prompt.format(
            context=context,
            question=question,
        )
        
        # Step 5: Get answer from Groq (with rate limiting)
        response = invoke_with_retry(self.llm, formatted_prompt)
        
        # Step 6: Extract source information (with re-ranker scores)
        sources = []
        for i, doc in enumerate(docs):
            sources.append({
                "page": doc.metadata.get("page", "?"),
                "type": doc.metadata.get("type", "unknown"),
                "text": doc.page_content[:500],
                "score": scores[i] if i < len(scores) else 0.0,  # Re-ranker score
            })
        
        # Step 7: Calculate confidence score
        confidence = self._calculate_confidence(response.content, scores)
        
        return {
            "answer": response.content,
            "sources": sources,
            "confidence": confidence,
        }
    
    def _calculate_confidence(self, answer: str, reranker_scores: list[float]) -> dict:
        """
        Calculate confidence score for the answer.
        
        Factors:
          - Average re-ranker score of top-3 chunks
          - LLM uncertainty signals (e.g. "I could not find")
        
        Returns:
            {
                "score": float (0-1),
                "level": str ("HIGH", "MEDIUM", "LOW"),
                "explanation": str
            }
        """
        # Factor 1: Average re-ranker score (top-3)
        top3_scores = reranker_scores[:3] if len(reranker_scores) >= 3 else reranker_scores
        avg_reranker_score = sum(top3_scores) / len(top3_scores) if top3_scores else 0.0
        
        # Factor 2: Detect uncertainty in LLM response
        uncertainty_phrases = [
            "could not find",
            "not in the document",
            "information is not available",
            "unclear",
            "uncertain",
        ]
        has_uncertainty = any(phrase in answer.lower() for phrase in uncertainty_phrases)
        
        # Combine factors
        if has_uncertainty:
            confidence_score = min(avg_reranker_score * 0.5, 0.4)  # Cap at MEDIUM if uncertain
        else:
            confidence_score = avg_reranker_score
        
        # Classify into levels
        if confidence_score >= 0.7:
            level = "HIGH"
            explanation = "Strong match between question and retrieved context"
        elif confidence_score >= 0.4:
            level = "MEDIUM"
            explanation = "Moderate relevance of retrieved context"
        else:
            level = "LOW"
            explanation = "Weak match or uncertain answer"
        
        return {
            "score": round(confidence_score, 2),
            "level": level,
            "explanation": explanation,
        }


def build_rag_chain(vectorstore: FAISS, documents: list) -> RAGChain:
    """
    Build and return a RAG chain with hybrid retrieval.
    
    Args:
        vectorstore: FAISS vector store
        documents: All document chunks (for BM25 indexing)
    """
    return RAGChain(vectorstore, documents)


def ask_question(chain: RAGChain, question: str) -> dict:
    """Convenience wrapper — ask a question on the chain."""
    return chain.ask(question)
