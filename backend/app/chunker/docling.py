import uuid
from typing import Any

from docling.chunking import HybridChunker

# Reusable chunker instance to avoid reloading HuggingFace tokenizer on every document.
# Cap chunk size at ~400 tokens (MiniLM maximum sequence length is 512; prevents truncation)
_chunker = HybridChunker()
_chunker.tokenizer.max_tokens = 400


class DoclingChunker:

    @staticmethod
    def chunk_docment(document: Any, file_name: str, user_id, doc_id):
        # Support both a single DoclingDocument or a list of batched DoclingDocuments
        docs = document if isinstance(document, list) else [document]

        all_chunks = []
        for doc in docs:
            all_chunks.extend(list(_chunker.chunk(doc)))

        if not all_chunks:
            return []

        return [
            {
                "text": chunk.text,
                "meta": {
                    "chunk_id": str(uuid.uuid4()),
                    "doc_id": str(doc_id),
                    "user_id": str(user_id),
                    "file_name": file_name,
                    "page_no": (
                        chunk.meta.doc_items[0].prov[0].page_no
                        if (chunk.meta.doc_items and chunk.meta.doc_items[0].prov)
                        else 1
                    ),
                    "headings": " > ".join(chunk.meta.headings) if chunk.meta.headings else "",
                }
            } for chunk in all_chunks
        ]
