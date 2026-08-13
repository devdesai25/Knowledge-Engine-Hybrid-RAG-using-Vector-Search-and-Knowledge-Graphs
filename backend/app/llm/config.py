from dataclasses import dataclass

@dataclass(frozen=True)
class GenerationConfig:
    model: str = "gemini-3-flash-preview"
    temperature: float = 0.2
    max_output_tokens: int = 1024
    top_p: float = 0.95

    system_instruction: str = (
        "You are an enterprise document assistant. Answer questions using "
        "only the provided context excerpts from company PDF documents. "
        "Cite the source document and page number when available. "
        "If the context does not contain enough information to answer "
        "confidently, say so explicitly rather than speculating. "
        "Do not reveal information from outside the provided context, "
        "even if you know it from general knowledge."
    )