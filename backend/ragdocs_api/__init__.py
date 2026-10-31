from flask import Flask
from flask_cors import CORS

from .config import Config
from .errors import register_error_handlers
from .extensions import db, jwt
from .routes import register_blueprints
from .services.demo_service import ensure_demo_user


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    CORS(
        app,
        resources={
            r"/api/*": {
                "origins": app.config["CORS_ORIGINS"],
                "allow_headers": ["Authorization", "Content-Type"],
                "methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            }
        },
    )

    db.init_app(app)
    jwt.init_app(app)

    register_error_handlers(app)
    register_blueprints(app)

    with app.app_context():
        db.create_all()
        ensure_demo_user()

    return app
