import pymupdf

from backend.app.extractor.base import BaseExtractor

class PDFExtractor(BaseExtractor):

    async def extract(self, file):

        pdf_bytes = await file.read()

        with pymupdf.open(
            stream=pdf_bytes,
            filetype="pdf"
        ) as doc:

            text = ""

            for page in doc:
                text += page.get_text()

        return text