from langchain_chroma import Chroma

from app.config import get_settings
from app.rag.embeddings import LocalSentenceTransformerEmbeddings

_store: Chroma | None = None


def get_vectorstore() -> Chroma:
    global _store
    if _store is None:
        settings = get_settings()
        _store = Chroma(
            collection_name="course_materials",
            embedding_function=LocalSentenceTransformerEmbeddings(),
            persist_directory=str(settings.resolved_path(settings.chroma_dir)),
        )
    return _store
