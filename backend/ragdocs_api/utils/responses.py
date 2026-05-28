from flask import jsonify


def error_response(message, status_code=400):
    return jsonify({"error": message}), status_code
