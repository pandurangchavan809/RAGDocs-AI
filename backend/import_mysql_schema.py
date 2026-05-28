from pathlib import Path
from urllib.parse import urlparse
from urllib.parse import quote_plus

from dotenv import load_dotenv
import os
import pymysql

BASE_DIR = Path(__file__).resolve().parent
SCHEMA_FILE = BASE_DIR.parent / "mysql_schema.sql"

load_dotenv(BASE_DIR / ".env")


def load_schema():
    return SCHEMA_FILE.read_text(encoding="utf-8")


def parse_database_url():
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        mysql_host = os.getenv("MYSQL_HOST", "").strip()
        mysql_port = os.getenv("MYSQL_PORT", "3306").strip()
        mysql_user = os.getenv("MYSQL_USER", "").strip()
        mysql_password = os.getenv("MYSQL_PASSWORD", "")
        mysql_database = os.getenv("MYSQL_DATABASE", "").strip()

        if not all([mysql_host, mysql_user, mysql_database]):
            raise ValueError(
                "Set DATABASE_URL or MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, and MYSQL_DATABASE."
            )

        database_url = (
            f"mysql+pymysql://{mysql_user}:{quote_plus(mysql_password)}"
            f"@{mysql_host}:{mysql_port}/{mysql_database}?charset=utf8mb4"
        )

    if not database_url.startswith("mysql+pymysql://"):
        raise ValueError("DATABASE_URL must be a mysql+pymysql URL.")

    parsed = urlparse(database_url.replace("mysql+pymysql://", "mysql://", 1))
    return {
        "host": parsed.hostname,
        "port": parsed.port or 3306,
        "user": parsed.username,
        "password": parsed.password,
        "database": parsed.path.lstrip("/"),
    }


def split_sql_statements(schema_text):
    statements = []
    current_lines = []

    for line in schema_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue

        current_lines.append(line)
        if stripped.endswith(";"):
            statements.append("\n".join(current_lines))
            current_lines = []

    if current_lines:
        statements.append("\n".join(current_lines))

    return statements


def main():
    config = parse_database_url()
    if not config["password"] or "REPLACE_WITH_YOUR_AIVEN_PASSWORD" in config["password"]:
        raise ValueError("Update backend/.env with your real Aiven password first.")

    connection = pymysql.connect(
        host=config["host"],
        port=config["port"],
        user=config["user"],
        password=config["password"],
        database=config["database"],
        charset="utf8mb4",
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor,
    )

    try:
        with connection.cursor() as cursor:
            for statement in split_sql_statements(load_schema()):
                cursor.execute(statement)
        print("Schema imported successfully.")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
