from flask import Blueprint, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt_identity,
    jwt_required,
)
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db
from ..models import User
from ..utils.responses import error_response

auth_bp = Blueprint("auth", __name__)


@auth_bp.post("/auth/register")
def register():
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not name or not email or not password:
        return error_response("Name, email, and password are required.")

    if User.query.filter_by(email=email).first():
        return error_response("An account with this email already exists.", 409)

    user = User(
        name=name,
        email=email,
        password_hash=generate_password_hash(password),
    )
    db.session.add(user)
    db.session.commit()

    return (
        jsonify(
            {
                "message": "Account created successfully. Please log in.",
                "user": {"id": user.id, "name": user.name, "email": user.email},
            }
        ),
        201,
    )


@auth_bp.post("/auth/login")
def login():
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    user = User.query.filter_by(email=email).first()
    if not user or not check_password_hash(user.password_hash, password):
        return error_response("Invalid email or password.", 401)

    return jsonify(
        {
            "token": create_access_token(identity=str(user.id)),
            "refresh_token": create_refresh_token(identity=str(user.id)),
            "user": {"id": user.id, "name": user.name, "email": user.email},
        }
    )


@auth_bp.post("/auth/refresh")
@jwt_required(refresh=True)
def refresh():
    user = db.session.get(User, int(get_jwt_identity()))
    if not user:
        return error_response("This account no longer exists.", 401)

    return jsonify({"token": create_access_token(identity=str(user.id))})
