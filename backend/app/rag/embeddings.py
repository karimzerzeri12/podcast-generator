from langchain_core.embeddings import Embeddings
from sentence_transformers import SentenceTransformer

_MODEL_NAME = "all-MiniLM-L6-v2"
_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(_MODEL_NAME)
    return _model


class LocalSentenceTransformerEmbeddings(Embeddings):
    """Local, free embeddings used for RAG chunk retrieval — kept separate from the
    Gemini calls so the free-tier LLM quota is reserved for script generation."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return _get_model().encode(texts).tolist()

    def embed_query(self, text: str) -> list[float]:
        return _get_model().encode([text])[0].tolist()
