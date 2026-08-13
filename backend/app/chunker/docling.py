from typing import Any

from docling.chunking import HybridChunker

class DoclingChunker():

    @staticmethod
    def chunk_docment(document: Any):

        chunker = HybridChunker()

        chunks = list(chunker.chunk(document))
        
        return [
            {
                "text": chunk.text,
                "meta": {
                    "page_no": chunk.meta.doc_items[0].prov[0].page_no,
                    "headings": chunk.meta.headings
                }
            } for chunk in chunks
        ]
      