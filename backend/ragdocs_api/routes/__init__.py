from .auth import auth_bp
from .chat import chat_bp
from .documents import documents_bp


def register_blueprints(app):
    app.register_blueprint(auth_bp, url_prefix="/api")
    app.register_blueprint(documents_bp, url_prefix="/api")
    app.register_blueprint(chat_bp, url_prefix="/api")
