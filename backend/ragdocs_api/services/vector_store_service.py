import os
from functools import lru_cache

from langchain_chroma import Chroma
from langchain_core.embeddings import Embeddings

from ..config import CHROMA_DIR, INDEX_VERSION
from .gemini_service import get_gemini_client


class GeminiEmbeddings(Embeddings):
    def __init__(self, model_name):
        self.model_name = model_name

    def _embed_text(self, text):
        client = get_gemini_client()
        response = client.models.embed_content(
            model=self.model_name,
            contents=text,
        )
        return response.embeddings[0].values

    def embed_documents(self, texts):
        return [self._embed_text(f"title: pdf chunk | text: {text}") for text in texts]

    def embed_query(self, text):
        return self._embed_text(f"task: question answering | query: {text}")


@lru_cache(maxsize=1)
def get_embedding_model():
    return GeminiEmbeddings(
        model_name=os.getenv("EMBEDDING_MODEL", "gemini-embedding-2").strip()
    )


def get_embedding_collection_name():
    model_name = os.getenv("EMBEDDING_MODEL", "gemini-embedding-2").strip()
    safe_name = model_name.replace("-", "_").replace("/", "_")
    return f"documents_{safe_name}_{INDEX_VERSION}"


def get_vector_store(user_id):
    user_store_dir = CHROMA_DIR / f"user_{user_id}"
    user_store_dir.mkdir(parents=True, exist_ok=True)
    return Chroma(
        collection_name=get_embedding_collection_name(),
        persist_directory=str(user_store_dir),
        embedding_function=get_embedding_model(),
    )
