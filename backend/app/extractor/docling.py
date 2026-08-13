import asyncio
from pathlib import Path
from tempfile import NamedTemporaryFile

from docling.document_converter import DocumentConverter

from .base import BaseExtractor

from backend.app.exceptions import ExtractionError

class DoclingExtractor(BaseExtractor):

    def __init__(self):
        self.convertor = DocumentConverter()

    async def extract(self, file):
        try:
            suffix = Path(file.filename).suffix

            with NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
                temp_file.write(await file.read())
                temp_path = temp_file.name

            try:
                result = await asyncio.to_thread(self.convertor.convert(temp_path))
                return result.document
            finally:
                Path(temp_path).unlink(missing_ok=True)

        except Exception as e:

            logger.info(
                "Processing failed for %s",
                file.filename
            )

            raise ExtractionError(
                "Failed to extract document."
            ) from e