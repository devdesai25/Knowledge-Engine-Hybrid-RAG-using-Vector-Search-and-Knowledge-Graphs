from .docling import DoclingExtractor

# Single shared extractor instance to avoid instantiating 20+ redundant DocumentConverters in memory
_default_extractor = DoclingExtractor()

EXTRACTOR_REGISTRY = {
    # Documents
    "application/pdf": _default_extractor,
    "image/jpeg": _default_extractor,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": _default_extractor,
    "application/msword": _default_extractor,
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": _default_extractor,
    "application/vnd.ms-excel": _default_extractor,
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": _default_extractor,
    "application/vnd.ms-powerpoint": _default_extractor,
    "application/vnd.oasis.opendocument.text": _default_extractor,
    "application/vnd.oasis.opendocument.spreadsheet": _default_extractor,
    "application/vnd.oasis.opendocument.presentation": _default_extractor,
    "application/epub+zip": _default_extractor,

    # Markup
    "text/plain": _default_extractor,
    "text/markdown": _default_extractor,
    "text/html": _default_extractor,
    "application/xhtml+xml": _default_extractor,
    "text/csv": _default_extractor,
    "application/json": _default_extractor,
    "application/xml": _default_extractor,
    
    # Email
    "message/rfc822": _default_extractor,
    "application/vnd.ms-outlook": _default_extractor,
}
