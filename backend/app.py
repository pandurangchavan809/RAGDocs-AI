from ragdocs_api import create_app
from ragdocs_api.extensions import db, jwt
from ragdocs_api.models import ChatMessage, Document, User
from ragdocs_api.services.gemini_service import get_gemini_config
from ragdocs_api.services.vector_store_service import get_embedding_collection_name

app = create_app()

__all__ = [
    "app",
    "db",
    "jwt",
    "User",
    "Document",
    "ChatMessage",
    "get_gemini_config",
    "get_embedding_collection_name",
]


if __name__ == "__main__":
    app.run(debug=True, port=5000)
