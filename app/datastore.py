import sqlite3
from pathlib import Path
from typing import Iterable, List

from .models import Program


class DataStore:
    """SQLite-backed storage for program definitions and execution history."""

    def __init__(self, db_path: Path = Path("data/registry.db")) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS programs (
                    program_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    importance INTEGER DEFAULT 0,
                    input_channel TEXT,
                    output_channel TEXT,
                    code_path TEXT,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    program_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    output TEXT,
                    started_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    finished_at TEXT,
                    FOREIGN KEY(program_id) REFERENCES programs(program_id)
                );
                """
            )
            conn.commit()

    def upsert_program(self, program: Program) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO programs (
                    program_id, name, description, importance, input_channel, output_channel, code_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(program_id) DO UPDATE SET
                    name=excluded.name,
                    description=excluded.description,
                    importance=excluded.importance,
                    input_channel=excluded.input_channel,
                    output_channel=excluded.output_channel,
                    code_path=excluded.code_path,
                    updated_at=CURRENT_TIMESTAMP;
                """,
                program.as_db_tuple(),
            )
            conn.commit()

    def list_programs(self) -> List[Program]:
        with self.connect() as conn:
            cur = conn.execute(
                """
                SELECT program_id, name, description, importance, input_channel, output_channel, code_path
                FROM programs
                ORDER BY importance DESC, name;
                """
            )
            rows = cur.fetchall()
            return [Program.from_db_row(row) for row in rows]

    def get_program(self, program_id: str) -> Program | None:
        with self.connect() as conn:
            cur = conn.execute(
                """
                SELECT program_id, name, description, importance, input_channel, output_channel, code_path
                FROM programs
                WHERE program_id = ?;
                """,
                (program_id,),
            )
            row = cur.fetchone()
            return Program.from_db_row(row) if row else None

    def log_run(self, program_id: str, status: str, output: str | None) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO runs (program_id, status, output, finished_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP);
                """,
                (program_id, status, output),
            )
            conn.commit()

    def list_runs(self, limit: int = 50, program_id: str | None = None) -> List[tuple]:
        query = [
            "SELECT id, program_id, status, output, started_at, finished_at",
            "FROM runs",
        ]
        params: list[str | int] = []

        if program_id:
            query.append("WHERE program_id = ?")
            params.append(program_id)

        query.append("ORDER BY id DESC")
        query.append("LIMIT ?")
        params.append(limit)

        statement = " ".join(query)

        with self.connect() as conn:
            cur = conn.execute(statement, params)
            return cur.fetchall()

    def bulk_register(self, programs: Iterable[Program]) -> None:
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT INTO programs (
                    program_id, name, description, importance, input_channel, output_channel, code_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(program_id) DO NOTHING;
                """,
                [program.as_db_tuple() for program in programs],
            )
            conn.commit()
