from dataclasses import dataclass

@dataclass(frozen=True)
class GenerationConfig:
    model: str = "deepseek-flash"
    temperature: float = 0.2
    max_output_tokens: int = 5120
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

    graph_system_instruction: str = (
            """
            You are a cypher query generator.
            
            You are given a user's natural language question and the available Neo4j graph Schema.

            Generate a read-only Cypher query that retrieves the information necessary to answer the question. 
            
            Use parameters rather than interpolating user values directly.
            
            Do not modify the database.

            """
        )
