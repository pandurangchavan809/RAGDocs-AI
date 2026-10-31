from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash

from ..extensions import db
from ..models import User

DEMO_NAME = "Demo User"
DEMO_EMAIL = "user@email.com"
DEMO_PASSWORD = "User@1234"


def ensure_demo_user():
    """Create the public demo account once. An existing account is left unchanged."""
    if User.query.filter_by(email=DEMO_EMAIL).first():
        return

    db.session.add(
        User(
            name=DEMO_NAME,
            email=DEMO_EMAIL,
            password_hash=generate_password_hash(DEMO_PASSWORD),
        )
    )
    try:
        db.session.commit()
    except IntegrityError:
        # Another server worker created it at the same moment.
        db.session.rollback()
