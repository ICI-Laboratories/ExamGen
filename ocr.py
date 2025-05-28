# MIT License — 2025
# Copyright (c) 2025
# Yohana Yamille Ornelas Ochoa, Kenya Alexandra Ramos Valadez,
# Pedro Antonio Ibarra Facio


import fitz 
from PIL import Image
from io import BytesIO
import easyocr
import logging

logger = logging.getLogger(__name__)
try:
    # Initialize reader only once
    reader = easyocr.Reader(['en', 'es'], gpu=True)
    logger.info("EasyOCR reader initialized successfully.")
except Exception as e:
    logger.error(f"Failed to initialize EasyOCR reader: {e}. OCR will likely fail.")
    reader = None


def extract_text_and_pages_with_ocr(file_bytes): # Pass file_bytes directly
    """
    Extracts text from each page of a PDF.
    Returns a list of dictionaries, each with 'page_number' and 'text'.
    Also returns total page count.
    """
    if reader is None:
        raise RuntimeError("EasyOCR reader is not initialized. Cannot perform OCR.")

    doc = fitz.open(stream=file_bytes, filetype="pdf")
    pages_data = []
    total_pages = len(doc)

    for page_num in range(total_pages):
        page_text_content = ""
        page = doc[page_num]
        
        # Attempt to extract text directly
        text = page.get_text()
        if text and text.strip():
            page_text_content = text
        else:  # If no direct text, perform OCR
            try:
                pix = page.get_pixmap(dpi=200)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                img_byte_arr = BytesIO()
                img.save(img_byte_arr, format="PNG")
                img_byte_arr = img_byte_arr.getvalue()
                
                ocr_results = reader.readtext(img_byte_arr, detail=0)
                page_text_content = " ".join(ocr_results)
            except Exception as ocr_page_err:
                logger.error(f"Error during OCR for page {page_num + 1}: {ocr_page_err}")
                page_text_content = f"[OCR Error on page {page_num + 1}]"

        pages_data.append({
            "page_number": page_num + 1, # 1-indexed for user display
            "text": page_text_content.strip()
        })
        logger.debug(f"Extracted text for page {page_num + 1} (length: {len(page_text_content)})")

    return pages_data, total_pages
