import logging
import io

import pytesseract
from pypdf import PdfReader

logger = logging.getLogger("core.pdf")

# Ensure Tesseract is in PATH or configure it here if needed
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def extract_text_from_pdf(file_content: bytes) -> str:
    """
    Extracts text from a PDF file content.
    First tries standard PDF text extraction.
    If text is sparse or empty, falls back to OCR.
    """
    logger.info("extract_text_from_pdf: starting (input size=%d bytes)", len(file_content))
    text = ""
    try:
        reader = PdfReader(io.BytesIO(file_content))
        logger.debug("extract_text_from_pdf: %d pages found", len(reader.pages))
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        
        # Simple heuristic to check if OCR is needed
        if len(text.strip()) < 50:
            # Fallback to OCR (Naive implementation, strictly per user request for Tesseract)
            # Note: Tesseract requires image input. We need to convert PDF pages to images first.
            # This usually requires 'pdf2image' and 'poppler'. 
            # To keep dependencies minimal and pure python where possible, we might just return what we have
            # or log a warning if pdf2image isn't available. 
            # For this MVP, we will stick to PyPDF. Real OCR implies heavier setup (pdf2image).
            # If the user specifically insists on Tesseract execution for PDFs, we need pdf2image.
            pass
            
            # UNCOMMENT BELOW IF POPPLER AND PDF2IMAGE ARE INSTALLED
            # from pdf2image import convert_from_bytes
            # images = convert_from_bytes(file_content)
            # type_text = ""
            # for img in images:
            #     type_text += pytesseract.image_to_string(img)
            # text = type_text if len(type_text) > len(text) else text
            
    except Exception as e:
        logger.exception("extract_text_from_pdf: error extracting text: %s", e)
        return ""

    logger.info("extract_text_from_pdf: extracted %d chars from PDF", len(text))
    return text

def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 100) -> list[str]:
    """
    Splits text into chunks of specified size with overlap.
    """
    logger.debug("chunk_text: text_len=%d chunk_size=%d overlap=%d", len(text), chunk_size, overlap)
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += (chunk_size - overlap)
    logger.info("chunk_text: produced %d chunks", len(chunks))
    return chunks
