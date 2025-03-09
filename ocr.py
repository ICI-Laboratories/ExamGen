import fitz  # PyMuPDF
from PIL import Image
from io import BytesIO
import easyocr

reader = easyocr.Reader(['en', 'es'], gpu=True)

def extract_text_with_ocr(file):
    """
    Extrae texto de un PDF. Si no hay texto directo, usa OCR con EasyOCR.
    """
    doc = fitz.open(stream=file.read(), filetype="pdf")
    extracted_text = ""

    for page_num in range(len(doc)):
        page = doc[page_num]
        # Intentar extraer texto directamente
        text = page.get_text()
        if text.strip():  # Si hay texto directo, usarlo
            extracted_text += text
        else:  # Si no hay texto, realizar OCR en la página como imagen
            pix = page.get_pixmap(dpi=200)  # Convertir página a imagen
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            # Convertir PIL Image a bytes
            img_bytes = BytesIO()
            img.save(img_bytes, format="PNG")
            img_bytes = img_bytes.getvalue()

            # Usar OCR para procesar la imagen
            ocr_text = " ".join(reader.readtext(img_bytes, detail=0))  # OCR
            extracted_text += ocr_text + "\n"

    return extracted_text
