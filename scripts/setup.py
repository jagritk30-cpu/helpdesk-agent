"""
Setup script — initializes PostgreSQL DB and ingests policy documents.
Run once after setting up your .env file.
"""

import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def run_sql_file(sql_file: Path):
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "helpdesk")
    user = os.getenv("POSTGRES_USER", "jagritpandit")
    password = os.getenv("POSTGRES_PASSWORD", "")

    env = os.environ.copy()
    if password:
        env["PGPASSWORD"] = password

    psql_cmd = "psql"
    # fallback to homebrew path if not found in path
    if not subprocess.run(["which", "psql"], capture_output=True).stdout:
        psql_cmd = "/opt/homebrew/bin/psql"

    cmd = [psql_cmd, "-h", host, "-p", port, "-U", user, "-d", db, "-f", str(sql_file)]
    result = subprocess.run(
        cmd,
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"[ERROR] psql failed:\n{result.stderr}")
        sys.exit(1)
    print(result.stdout)


def setup_db():
    print("=" * 60)
    print("Step 1: Setting up PostgreSQL database schema & seed data")
    print("=" * 60)
    sql_file = Path(__file__).parent / "init_db.sql"
    run_sql_file(sql_file)
    print("[OK] Database initialized.")


def ingest_policies():
    print("\n" + "=" * 60)
    print("Step 2: Ingesting policy documents into ChromaDB")
    print("=" * 60)
    from agent.rag import build_vectorstore
    build_vectorstore(force_rebuild=True)
    print("[OK] Policy documents ingested.")


if __name__ == "__main__":
    setup_db()
    ingest_policies()
    print("\n✅ Setup complete! Run the API with: uvicorn api:app --reload")
