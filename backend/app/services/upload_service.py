import logging
import asyncio
from time import perf_counter

import magic
from fastapi import UploadFile

from backend.app.exceptions import UnsupportedMimeTypeError, ExtractionError, EmbeddingError, UpsertError
from backend.app.extractor.registry import EXTRACTOR_REGISTRY
from backend.app.chunker.docling import DoclingChunker
from backend.app.embedder.embedding import generate_embedding
from backend.app.database.qdrant import upsert

logger = logging.getLogger(__name__)

MIME_SNIFF_SIZE = 2048

async def process_single_file(file: UploadFile) -> dict:
    start = perf_counter()

    try:
        data_chunk = await file.read(MIME_SNIFF_SIZE)
        mime_type = magic.from_buffer(data_chunk, mime=True)
        await file.seek(0)
        
        extractor =  EXTRACTOR_REGISTRY.get(mime_type)

        if extractor is None:
            raise UnsupportedMimeTypeError(
                f"Unsupported MIME TYPE: {mime_type}"
            )
        
        document = await extractor.extract(file)
    
        chunks = DoclingChunker.chunk_docment(document)

        if not chunks:
            raise ExtractionError(
                "Document contains no extractable text."
            )

        text = [chunk["text"] for chunk in chunks]

        embeddings = generate_embedding(text)
        
        result = await upsert(embeddings, chunks)

        elapsed = perf_counter() - start

        logger.info(
            "Processed %s | chunks %d | time: %.2fs",
            file.filename,
            len(chunks),
            elapsed
        )

        return {
            "filename": file.filename,
            "status": "success",
            "chunks": len(chunks),
        }

    except (
        UnsupportedMimeTypeError,
        ExtractionError,
        EmbeddingError,
        UpsertError
    ):

        logger.exception(
            "Processing failed for %s",
            file.filename
        ) 
        return {
            "filename": file.filename,
            "status": "failed",
            "error": "Processing failed."
        }

    except Exception:

        logger.exception(
            "Unexpected error while processing %s",
            file.filename
        )

        return {
            "filename": file.filename,
            "status": "failed",
            "error": "Processing failed."
        }

async def upload_service(files: list[UploadFile]) -> dict:

    results = await asyncio.gather(
        *(process_single_file(file) for file in files)
    )

    uploaded = sum(
        result["status"] == "success"
        for result in results
    )

    failed = len(results) - uploaded

    return {
        "uploaded": uploaded,
        "failed": failed,
        "details": results,
    }