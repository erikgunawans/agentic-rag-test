import fitz  # PyMuPDF
import tiktoken
from langsmith import traceable
from app.config import get_settings
from app.database import get_supabase_client
from app.services.embedding_service import EmbeddingService

settings = get_settings()
embedding_service = EmbeddingService()


def parse_text(file_bytes: bytes, mime_type: str) -> str:
    if mime_type == "application/pdf":
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        text = "".join(page.get_text() for page in doc)
        doc.close()
        return text
    # TXT or Markdown
    return file_bytes.decode("utf-8", errors="ignore")


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
    doc_id: str, user_id: str, file_path: str, mime_type: str, embedding_model: str | None = None
):
    client = get_supabase_client()
    try:
        client.table("documents").update({"status": "processing"}).eq("id", doc_id).execute()

        # Download from Supabase Storage
        file_bytes = client.storage.from_(settings.storage_bucket).download(file_path)

        # Parse and chunk
        text = parse_text(file_bytes, mime_type)
        if not text.strip():
            raise ValueError("No text content extracted from file")

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
        }).eq("id", doc_id).execute()

    except Exception as e:
        client.table("documents").update({
            "status": "failed",
            "error_msg": str(e)[:500],
        }).eq("id", doc_id).execute()
