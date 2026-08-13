from google import genai
from google.genai import types
from google.genai.errors import APIError

from backend.app.settings import setting
from backend.app.exceptions import GenerationError, LLMTimeoutError
from backend.app.llm.config import GenerationConfig as AppGenerationConfig
from backend.app.llm.format import format_chunk

class LLMClient:

    def __init__(self, config: AppGenerationConfig | None = None):
        self._config = config or AppGenerationConfig()
        self._client = genai.Client(
            api_key=setting.gemini_api_key.get_secret_value()
        )

    def generate(self, query: str, context_chunks: list[str]) -> str:

        context_block = "\n\n--\n\n".join(format_chunk(chunk) for chunk in context_chunks.points)

        prompt = f"Context: \n{context_block}\n\nQuestion:\n{query}"

        try:
            response = self._client.models.generate_content(
                model=self._config.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=self._config.system_instruction,
                    temperature=self._config.temperature,
                    max_output_tokens=self._config.max_output_tokens,
                    top_p=self._config.top_p
                ),
            )

        except TimeoutError as e:
            raise LLMTimeoutError(f"Gemini request timed out : {e}") from e

        except APIError as e:
            raise GenerationError(f"Gemini generation failed: {e}") from e

        if not response.text:
            raise GenerationError("Gemini returned empty response")

        return response.text