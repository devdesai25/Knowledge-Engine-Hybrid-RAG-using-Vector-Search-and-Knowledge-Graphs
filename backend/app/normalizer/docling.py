import re
import unicodedata

from .base import BaseNormalizer

class DoclingNormalizer(BaseNormalizer):

    CONTROL_CHARS = re.compile(
        r"[\x01-\x08\x0B\x0C\x0E-\x1F\x7F]"
    )

    async def normalize(self, document):
        
        return 