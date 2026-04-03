import csv
import io
import json
import logging
import fitz  # PyMuPDF
import tiktoken
from docx import Document as DocxDocument
from bs4 import BeautifulSoup
from langsmith import traceable
from app.config import get_settings
from app.database import get_supabase_client
from app.services.embedding_service import EmbeddingService
from app.services.metadata_service import MetadataService

logger = logging.getLogger(__name__)

settings = get_settings()
embedding_service = EmbeddingService()
metadata_service = MetadataService()


def parse_text(file_bytes: bytes, mime_type: str) -> str:
    if mime_type == "application/pdf":
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        text = "".join(page.get_text() for page in doc)
        doc.close()
        return text
    if mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        return _parse_docx(file_bytes)
    if mime_type == "text/csv":
        return _parse_csv(file_bytes)
    if mime_type == "text/html":
        return _parse_html(file_bytes)
    if mime_type == "application/json":
        return _parse_json(file_bytes)
    # TXT or Markdown
    return file_bytes.decode("utf-8", errors="ignore")


def _parse_docx(file_bytes: bytes) -> str:
    doc = DocxDocument(io.BytesIO(file_bytes))
    parts = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            parts.append(text)
    for table in doc.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                parts.append(" | ".join(cells))
    return "\n".join(parts)


def _parse_csv(file_bytes: bytes) -> str:
    text = file_bytes.decode("utf-8", errors="ignore")
    reader = csv.reader(io.StringIO(text))
    return "\n".join(" | ".join(row) for row in reader)


def _parse_html(file_bytes: bytes) -> str:
    text = file_bytes.decode("utf-8", errors="ignore")
    soup = BeautifulSoup(text, "html.parser")
    for element in soup(["script", "style"]):
        element.decompose()
    return soup.get_text(separator="\n", strip=True)


def _parse_json(file_bytes: bytes) -> str:
    text = file_bytes.decode("utf-8", errors="ignore")
    data = json.loads(text)
    return json.dumps(data, indent=2, ensure_ascii=False)


def chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    enc = tiktoken.get_encoding("cl100k_base")
    tokens = enc.encode(text)
    chunks = []
    start = 0
    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))
        chunks.append(enc.decode(tokens[start:end]))
        if end == len(tokens):
            break
        start += chunk_size - chunk_overlap
    return [c for c in chunks if c.strip()]


@traceable
async def process_document(
    doc_id: str,
    user_id: str,
    file_path: str,
    mime_type: str,
    embedding_model: str | None = None,
    llm_model: str | None = None,
):
    client = get_supabase_client()
    try:
        client.table("documents").update({"status": "processing"}).eq("id", doc_id).eq("user_id", user_id).execute()

        # Download from Supabase Storage
        file_bytes = client.storage.from_(settings.storage_bucket).download(file_path)

        # Parse text
        text = parse_text(file_bytes, mime_type)
        if not text.strip():
            raise ValueError("No text content extracted from file")

        # Extract metadata (best-effort — failures are logged but don't block ingestion)
        metadata_dict = None
        try:
            metadata = await metadata_service.extract_metadata(text, model=llm_model)
            if metadata:
                metadata_dict = metadata.model_dump()
        except Exception as e:
            logger.warning("Metadata extraction skipped for doc_id=%s: %s", doc_id, e)

        # Chunk and embed
        chunks = chunk_text(text, settings.rag_chunk_size, settings.rag_chunk_overlap)
        if not chunks:
            raise ValueError("No chunks generated")

        # Embed in batches of 100 using the user's chosen embedding model
        all_embeddings: list[list[float]] = []
        for i in range(0, len(chunks), 100):
            batch_embeddings = await embedding_service.embed_batch(
                chunks[i : i + 100], model=embedding_model
            )
            all_embeddings.extend(batch_embeddings)

        # Bulk insert chunks
        client.table("document_chunks").insert([
            {
                "document_id": doc_id,
                "user_id": user_id,
                "content": chunk,
                "chunk_index": i,
                "embedding": embedding,
            }
            for i, (chunk, embedding) in enumerate(zip(chunks, all_embeddings))
        ]).execute()

        client.table("documents").update({
            "status": "completed",
            "chunk_count": len(chunks),
            "metadata": metadata_dict,
        }).eq("id", doc_id).eq("user_id", user_id).execute()

    except Exception as e:
        logger.error("Document processing failed for doc_id=%s: %s", doc_id, e)
        client.table("documents").update({
            "status": "failed",
            "error_msg": "Processing failed. Please try uploading again.",
        }).eq("id", doc_id).eq("user_id", user_id).execute()
