import base64
import io
import logging
from dataclasses import dataclass
import fitz  # PyMuPDF
from openai import AsyncOpenAI
from app.services.tracing_service import traced
from app.config import get_settings


@dataclass
class OcrResult:
    text: str
    pages_processed: int
    pages_failed: int
    ocr_used: bool = True

logger = logging.getLogger(__name__)
settings = get_settings()

_MIN_CHARS_PER_PAGE = 50  # Below this, page is likely scanned/image-only
_MAX_IMAGE_DIM = 1568      # OpenAI vision max recommended dimension
_OCR_SYSTEM_PROMPT = (
    "You are an OCR engine for Indonesian legal documents. "
    "Extract ALL text from this document page exactly as written. "
    "Preserve paragraph structure, headings (BAB, Pasal, Bagian), "
    "numbered lists, and table formatting. "
    "If text is unclear, mark it as [tidak terbaca]. "
    "Output only the extracted text, no commentary."
)


class VisionService:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)

    def is_scanned_pdf(self, file_bytes: bytes) -> bool:
        """Detect if a PDF is scanned (image-only) by checking text density."""
        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            if doc.page_count == 0:
                doc.close()
                return False
            total_chars = sum(len(page.get_text().strip()) for page in doc)
            avg_chars = total_chars / doc.page_count
            doc.close()
            return avg_chars < _MIN_CHARS_PER_PAGE
        except Exception:
            return False

    def extract_page_images(self, file_bytes: bytes) -> list[bytes]:
        """Render each PDF page as a PNG image."""
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        images = []
        for page in doc:
            # Render at 150 DPI for good OCR quality without huge images
            mat = fitz.Matrix(150 / 72, 150 / 72)
            pix = page.get_pixmap(matrix=mat)
            # Downscale if too large
            if pix.width > _MAX_IMAGE_DIM or pix.height > _MAX_IMAGE_DIM:
                scale = _MAX_IMAGE_DIM / max(pix.width, pix.height)
                mat = fitz.Matrix(scale * 150 / 72, scale * 150 / 72)
                pix = page.get_pixmap(matrix=mat)
            images.append(pix.tobytes("png"))
        doc.close()
        return images

    @traced(name="vision_ocr_page")
    async def ocr_page(self, image_bytes: bytes, page_num: int) -> str:
        """OCR a single page image using OpenAI vision API."""
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        response = await self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": _OCR_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"Extract all text from page {page_num + 1} of this Indonesian legal document.",
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{b64}",
                                "detail": "high",
                            },
                        },
                    ],
                },
            ],
            temperature=0,
            max_tokens=4096,
        )
        return response.choices[0].message.content or ""

    @traced(name="vision_ocr_pdf")
    async def ocr_pdf(self, file_bytes: bytes) -> OcrResult:
        """OCR an entire scanned PDF, returning structured result."""
        page_images = self.extract_page_images(file_bytes)
        logger.info("OCR: processing %d pages", len(page_images))

        pages_text = []
        pages_failed = 0
        for i, img in enumerate(page_images):
            try:
                text = await self.ocr_page(img, i)
                if text.strip():
                    pages_text.append(f"--- Halaman {i + 1} ---\n{text}")
            except Exception as e:
                logger.warning("OCR failed for page %d: %s", i + 1, e)
                pages_text.append(f"--- Halaman {i + 1} ---\n[OCR gagal: {e}]")
                pages_failed += 1

        return OcrResult(
            text="\n\n".join(pages_text),
            pages_processed=len(page_images),
            pages_failed=pages_failed,
        )
