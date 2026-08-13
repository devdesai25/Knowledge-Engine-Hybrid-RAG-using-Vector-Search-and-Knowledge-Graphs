from .docling import DoclingExtractor

EXTRACTOR_REGISTRY = {
    # Documents
    "application/pdf": DoclingExtractor(),
    "image/jpeg": DoclingExtractor(),
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": DoclingExtractor(),
    "application/msword": DoclingExtractor(),
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": DoclingExtractor(),
    "application/vnd.ms-excel": DoclingExtractor(),
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": DoclingExtractor(),
    "application/vnd.ms-powerpoint": DoclingExtractor(),
    "application/vnd.oasis.opendocument.text": DoclingExtractor(),
    "application/vnd.oasis.opendocument.spreadsheet": DoclingExtractor(),
    "application/vnd.oasis.opendocument.presentation": DoclingExtractor(),
    "application/epub+zip": DoclingExtractor(),

    # Markup
    "text/plain": DoclingExtractor(),
    "text/markdown": DoclingExtractor(),
    "text/html": DoclingExtractor(),
    "application/xhtml+xml": DoclingExtractor(),
    "text/csv": DoclingExtractor(),
    "application/json": DoclingExtractor(),
    "application/xml": DoclingExtractor(),
    
    # Email
    "message/rfc822": DoclingExtractor(),
    "application/vnd.ms-outlook": DoclingExtractor(),
    
}