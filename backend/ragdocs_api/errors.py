from sqlalchemy.exc import OperationalError

from .extensions import db
from .utils.responses import error_response


def register_error_handlers(app):
    @app.errorhandler(OperationalError)
    def handle_operational_error(error):
        db.session.remove()
        return error_response(
            "Database connection was interrupted. Please try again.",
            503,
        )
