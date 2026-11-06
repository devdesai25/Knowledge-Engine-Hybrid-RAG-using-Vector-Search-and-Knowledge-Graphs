import asyncio
import logging

from pathlib import Path
from tempfile import NamedTemporaryFile

import pypdfium2 as pdfium
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import ThreadedPdfPipelineOptions
from docling.datamodel.base_models import ConversionStatus, InputFormat
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend

from .base import BaseExtractor
from backend.app.core.exceptions.exceptions import ExtractionError

logger = logging.getLogger(__name__)

# Batch size of 5-10 pages for processing PDF documents in chunks
DEFAULT_PAGE_BATCH_SIZE = 10

class DoclingExtractor(BaseExtractor):

    def __init__(self, page_batch_size: int = DEFAULT_PAGE_BATCH_SIZE):
        self.page_batch_size = page_batch_size
        opts = ThreadedPdfPipelineOptions()
        opts.do_ocr = False
        opts.generate_page_images = False
        opts.images_scale = 1.0
        opts.layout_batch_size = 4
        opts.table_batch_size = 4
        opts.ocr_batch_size = 1
        opts.queue_max_size = 4

        self.convertor = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=opts,
                    backend=PyPdfiumDocumentBackend
                )
            }
        )
        self._sem = asyncio.Semaphore(1)

    async def extract(self, file):
        try:
            suffix = Path(file.filename).suffix.lower()

            with NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
                temp_file.write(await file.read())
                temp_path = temp_file.name

            try:
                # Batch extract pages for PDFs
                if suffix == ".pdf":
                    try:
                        pdf = pdfium.PdfDocument(temp_path)
                        total_pages = len(pdf)
                        pdf.close()
                    except Exception as e:
                        logger.warning(
                            "Failed to inspect PDF pages with pdfium: %s. Using default extraction.", e
                        )
                        total_pages = 0

                    if total_pages > self.page_batch_size:
                        logger.info(
                            "Extracting %s (%d pages) in batches of %d pages",
                            file.filename, total_pages, self.page_batch_size
                        )
                        documents = []
                        for start in range(1, total_pages + 1, self.page_batch_size):
                            end = min(start + self.page_batch_size - 1, total_pages)
                            logger.info("[DOCLING] %s: processing pages %d-%d of %d", file.filename, start, end, total_pages)
                            async with self._sem:
                                result = await asyncio.to_thread(
                                    self.convertor.convert,
                                    temp_path,
                                    page_range=(start, end),
                                )
                            if result.status not in (ConversionStatus.SUCCESS, ConversionStatus.PARTIAL_SUCCESS):
                                raise ExtractionError(f"Docling status: {result.status} for pages {start}-{end}")
                            documents.append(result.document)
                        return documents

                # Single conversion for non-PDFs or PDFs within page_batch_size
                async with self._sem:
                    result = await asyncio.to_thread(
                        self.convertor.convert,
                        temp_path,
                    )

                if result.status not in (ConversionStatus.SUCCESS, ConversionStatus.PARTIAL_SUCCESS):
                    raise ExtractionError(f"Docling status: {result.status}")

                return result.document

            finally:
                Path(temp_path).unlink(missing_ok=True)

        except Exception as e:
            logger.exception("Processing failed for %s", file.filename)
            raise ExtractionError("Failed to extract document.") from e
