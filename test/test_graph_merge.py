import pytest
from backend.app.schema.graph import GraphExtraction, Entity, Relationship
from backend.app.llm.client_er import LLMExtraction

def test_merge_graphs():
    g1 = GraphExtraction(
        entities=[
            Entity(name="Google", type="Organization", description="Search company"),
            Entity(name="TensorFlow", type="Technology", description="ML framework")
        ],
        relationships=[
            Relationship(source="Google", target="TensorFlow", type="DEVELOPED_BY", description="Google developed TF")
        ]
    )
    g2 = GraphExtraction(
        entities=[
            Entity(name="google", type="Organization", description="Alphabet subsidiary focused on AI and search"),
            Entity(name="PyTorch", type="Technology", description="ML framework")
        ],
        relationships=[
            Relationship(source="Google", target="TensorFlow", type="DEVELOPED_BY", description="Google created TensorFlow")
        ]
    )

    merged = LLMExtraction._merge_graphs([g1, g2])
    entity_names = {e.name for e in merged.entities}
    assert "Google" in entity_names
    assert "TensorFlow" in entity_names
    assert "PyTorch" in entity_names
    assert len(merged.entities) == 3
    assert len(merged.relationships) == 1
