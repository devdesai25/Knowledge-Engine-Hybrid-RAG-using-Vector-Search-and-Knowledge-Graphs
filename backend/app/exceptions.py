class UnsupportedMimeTypeError(Exception):
    pass

class ExtractionError(Exception):
    pass

class EmbeddingError(Exception):
    pass

class UpsertError(Exception):
    pass

class GenerationError(Exception):
    pass

class LLMTimeoutError(Exception):
    pass