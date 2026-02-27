"""
pdf_parser.py — Extract text and tables from SID PDFs.

WHY TWO LIBRARIES?
  - PyMuPDF (fitz): Fast text extraction, preserves reading order.
  - pdfplumber: Better at detecting and extracting tables.

We use both to get the best of each.
"""

import fitz  # PyMuPDF
import pdfplumber


def extract_text_with_pymupdf(pdf_path: str) -> list[dict]:
    """
    Extract text from each page using PyMuPDF.
    
    Returns a list of dicts, one per page:
      [{"page": 1, "text": "...", "type": "narrative"}, ...]
    """
    pages = []
    doc = fitz.open(pdf_path)
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")  # Plain text extraction
        
        # Skip empty pages (cover pages, blank pages)
        if text.strip():
            pages.append({
                "page": page_num + 1,       # 1-indexed for display
                "text": text.strip(),
                "type": "narrative"
            })
    
    doc.close()
    return pages


def extract_tables_with_pdfplumber(pdf_path: str) -> list[dict]:
    """
    Extract tables from the PDF using pdfplumber.
    
    Tables are converted to readable text format like:
      "Column1 | Column2 | Column3
       Value1  | Value2  | Value3"
    
    Returns:
      [{"page": 5, "text": "table text...", "type": "table"}, ...]
    """
    tables = []
    
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            page_tables = page.extract_tables()
            
            for table in page_tables:
                if not table:
                    continue
                
                # Convert table rows to pipe-separated text
                # This makes tables readable for the LLM
                table_text = ""
                for row in table:
                    # Replace None values with empty string
                    cleaned_row = [str(cell).strip() if cell else "" for cell in row]
                    table_text += " | ".join(cleaned_row) + "\n"
                
                if table_text.strip():
                    tables.append({
                        "page": page_num + 1,
                        "text": table_text.strip(),
                        "type": "table"
                    })
    
    return tables


def parse_pdf(pdf_path: str) -> list[dict]:
    """
    Main function: Parse a SID PDF and return all content.
    
    Combines:
      1. Page-by-page text from PyMuPDF
      2. Tables from pdfplumber
    
    Returns sorted list by page number.
    """
    print(f"[PDF] Parsing: {pdf_path}")
    
    # Step 1: Get narrative text
    pages = extract_text_with_pymupdf(pdf_path)
    print(f"   [OK] Extracted text from {len(pages)} pages")
    
    # Step 2: Get tables
    tables = extract_tables_with_pdfplumber(pdf_path)
    print(f"   [OK] Extracted {len(tables)} tables")
    
    # Step 3: Combine and sort by page
    all_content = pages + tables
    all_content.sort(key=lambda x: x["page"])
    
    return all_content
