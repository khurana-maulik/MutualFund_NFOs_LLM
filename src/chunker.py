"""
chunker.py — Split parsed PDF content into smaller chunks for embedding.

WHY CHUNKING MATTERS:
  - LLMs have limited context windows.
  - Smaller, focused chunks = better retrieval accuracy.
  - We need to preserve context (overlap) between chunks.

STRATEGY:
  - Narrative text → Split by paragraphs/sentences (RecursiveCharacterTextSplitter)
  - Tables → Keep as whole chunks (don't split tables!)
  - Every chunk gets metadata: page number, type, source file
"""

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from src.config import CHUNK_SIZE, CHUNK_OVERLAP


def create_chunks(parsed_pages: list[dict], source_filename: str) -> list[Document]:
    """
    Convert parsed PDF content into LangChain Document chunks.
    
    Args:
        parsed_pages: Output from pdf_parser.parse_pdf()
        source_filename: Name of the PDF file (for metadata)
    
    Returns:
        List of LangChain Document objects with metadata
    """
    
    # Text splitter for narrative content
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        # Split at these boundaries (in order of priority):
        # 1. Double newline (paragraph break)
        # 2. Single newline
        # 3. Sentence ending (. ! ?)
        # 4. Space (word boundary)
        separators=["\n\n", "\n", ". ", " ", ""],
        length_function=len,
    )
    
    all_chunks = []
    
    for page_data in parsed_pages:
        page_num = page_data["page"]
        text = page_data["text"]
        content_type = page_data["type"]
        
        # Common metadata for all chunks from this page
        base_metadata = {
            "source": source_filename,
            "page": page_num,
            "type": content_type,
        }
        
        if content_type == "table":
            # ✅ Tables: Keep as ONE chunk (don't split!)
            # Splitting a table would destroy its meaning
            doc = Document(
                page_content=f"[Table from page {page_num}]\n{text}",
                metadata=base_metadata,
            )
            all_chunks.append(doc)
        
        else:
            # ✅ Narrative text: Split into smaller chunks
            splits = text_splitter.create_documents(
                texts=[text],
                metadatas=[base_metadata],
            )
            all_chunks.extend(splits)
    
    print(f"   ✅ Created {len(all_chunks)} chunks from '{source_filename}'")
    return all_chunks
