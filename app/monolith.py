"""
نسخة ملفٍ واحد تجمع جميع المكونات (النماذج، التخزين، التنفيذ، وواجهة الأوامر)
للاستخدام السريع أو النسخ في بيئات أخرى بدون الاعتماد على ملفات متعددة.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Iterable, List, Optional


# ------------------------------
# النماذج Models
# ------------------------------
@dataclass
class Program:
    """تمثيل برنامج فرعي يديره المنظّم."""

    program_id: str
    name: str
    description: str = ""
    importance: int = 0
    input_channel: str = ""
    output_channel: str = ""
    code_path: Optional[str] = None

    def as_db_tuple(self) -> tuple:
        return (
            self.program_id,
            self.name,
            self.description,
            self.importance,
            self.input_channel,
            self.output_channel,
            self.code_path,
        )

    @classmethod
    def from_db_row(cls, row: tuple) -> "Program":
        return cls(
            program_id=row[0],
            name=row[1],
            description=row[2] or "",
            importance=row[3] or 0,
            input_channel=row[4] or "",
            output_channel=row[5] or "",
            code_path=row[6],
        )


# ------------------------------
# التخزين Storage
# ------------------------------
class DataStore:
    """تخزين يعتمد SQLite لتعريف البرامج وسجلّ التشغيل."""

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


# ------------------------------
# التسجيل Registry
# ------------------------------
class ProgramRegistry:
    """يدير تسجيل واستعلام برامج المنظّم."""

    def __init__(self, datastore: DataStore):
        self.datastore = datastore

    def initialize(self) -> None:
        self.datastore.initialize()

    def register(self, program: Program) -> None:
        self.datastore.upsert_program(program)

    def bulk_register(self, programs: Iterable[Program]) -> None:
        self.datastore.bulk_register(programs)

    def list_programs(self) -> List[Program]:
        return self.datastore.list_programs()

    def get(self, program_id: str) -> Program | None:
        return self.datastore.get_program(program_id)


# ------------------------------
# التنفيذ Executor
# ------------------------------
class ProgramExecutor:
    """ينفّذ البرامج الفرعية ويسجّل نتائجها."""

    def __init__(self, datastore: DataStore):
        self.datastore = datastore

    def _load_callable_from_path(self, code_path: str) -> Callable[[dict], Any]:
        path = Path(code_path)
        if not path.exists():
            raise FileNotFoundError(f"Code file not found: {code_path}")

        spec = importlib.util.spec_from_file_location(path.stem, path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot import code from {code_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore[arg-type]
        return self._extract_runner(module, code_path)

    def _extract_runner(self, module: ModuleType, code_path: str) -> Callable[[dict], Any]:
        if not hasattr(module, "run"):
            raise AttributeError(
                f"The module {code_path} must expose a callable named 'run(payload: dict)'"
            )
        runner = getattr(module, "run")
        if not callable(runner):
            raise TypeError("The 'run' attribute must be callable")
        return runner

    def execute_inline(self, program: Program, code: str, payload: dict[str, Any]) -> Any:
        local_scope: dict[str, Any] = {}
        exec(code, {}, local_scope)
        if "run" not in local_scope or not callable(local_scope["run"]):
            raise AttributeError("Inline code must define a callable named 'run(payload: dict)'")
        runner = local_scope["run"]
        return self._execute(program, runner, payload)

    def execute_registered(self, program: Program, payload: dict[str, Any]) -> Any:
        if not program.code_path:
            raise ValueError("No code_path set for this program")
        runner = self._load_callable_from_path(program.code_path)
        return self._execute(program, runner, payload)

    def _execute(self, program: Program, runner: Callable[[dict], Any], payload: dict[str, Any]) -> Any:
        try:
            output = runner(payload)
            serialized = json.dumps(output, ensure_ascii=False, default=str)
            self.datastore.log_run(program.program_id, "success", serialized)
            return output
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self.datastore.log_run(program.program_id, "failure", str(exc))
            raise


# ------------------------------
# واجهة سطر الأوامر CLI
# ------------------------------
ECHO_SAMPLE_CODE = """
from __future__ import annotations

def run(payload: dict) -> dict:
    text = payload.get("text", "")
    count = int(payload.get("count", 1))
    return {
        "echo": text,
        "repeat": count,
        "message": f"Received '{text}' repeated {count} time(s)",
    }
"""


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Monolithic orchestrator for managing and executing many subprograms",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_cmd = subparsers.add_parser("init-db", help="Initialize the SQLite registry database")
    init_cmd.add_argument("--db", type=Path, default=Path("data/registry.db"))

    register_cmd = subparsers.add_parser("register", help="Register or update a subprogram definition")
    register_cmd.add_argument("program_id")
    register_cmd.add_argument("name")
    register_cmd.add_argument("--description", default="")
    register_cmd.add_argument("--importance", type=int, default=0)
    register_cmd.add_argument("--input-channel", default="")
    register_cmd.add_argument("--output-channel", default="")
    register_cmd.add_argument("--code-path", type=Path)
    register_cmd.add_argument("--db", type=Path, default=Path("data/registry.db"))

    bulk_cmd = subparsers.add_parser("bulk-register", help="Register programs from a JSONL file")
    bulk_cmd.add_argument("jsonl_path", type=Path)
    bulk_cmd.add_argument("--db", type=Path, default=Path("data/registry.db"))

    list_cmd = subparsers.add_parser("list", help="List all registered subprograms")
    list_cmd.add_argument("--db", type=Path, default=Path("data/registry.db"))

    runs_cmd = subparsers.add_parser("runs", help="List recent execution history")
    runs_cmd.add_argument("--db", type=Path, default=Path("data/registry.db"))
    runs_cmd.add_argument("--program-id", dest="program_id")
    runs_cmd.add_argument("--limit", type=int, default=20)

    run_cmd = subparsers.add_parser("run", help="Execute a registered subprogram")
    run_cmd.add_argument("program_id")
    run_cmd.add_argument("payload", help="JSON payload passed to the subprogram")
    run_cmd.add_argument("--db", type=Path, default=Path("data/registry.db"))

    inline_cmd = subparsers.add_parser(
        "run-inline", help="Execute inline code without persisting it as a file"
    )
    inline_cmd.add_argument("program_id")
    inline_cmd.add_argument("payload", help="JSON payload passed to the subprogram")
    inline_cmd.add_argument("code", help="Python code that defines a run(payload) function")
    inline_cmd.add_argument("--db", type=Path, default=Path("data/registry.db"))

    demo_cmd = subparsers.add_parser(
        "demo", help="Initialize, register, and execute the bundled echo sample (inline)"
    )
    demo_cmd.add_argument("--db", type=Path, default=Path("data/registry.db"))
    demo_cmd.add_argument("--text", default="hello")
    demo_cmd.add_argument("--count", type=int, default=2)

    preview_cmd = subparsers.add_parser(
        "preview-code", help="عرض ملف كود كامل مع ترقيم الأسطر للمعاينة"
    )
    preview_cmd.add_argument(
        "--file",
        type=Path,
        default=Path(__file__).parent,
        help="مسار ملف الكود المراد عرضه. يمكن تمرير مجلد لعرض الملف الموحّد تلقائيًا.",
    )
    preview_cmd.add_argument(
        "--start", type=int, default=1, help="رقم أول سطر لعرضه (1 افتراضيًا)"
    )
    preview_cmd.add_argument(
        "--end",
        type=int,
        help="رقم آخر سطر لعرضه (يُعرَض كامل الملف إذا تُرك فارغًا)",
    )

    return parser


def _load_payload(raw_payload: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON payload: {exc}")
    if not isinstance(payload, dict):
        raise SystemExit("Payload must be a JSON object")
    return payload


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    datastore = DataStore(args.db)
    registry = ProgramRegistry(datastore)
    executor = ProgramExecutor(datastore)

    if args.command == "init-db":
        registry.initialize()
        print(f"Initialized database at {args.db}")
        return

    registry.initialize()

    if args.command == "register":
        program = Program(
            program_id=args.program_id,
            name=args.name,
            description=args.description,
            importance=args.importance,
            input_channel=args.input_channel,
            output_channel=args.output_channel,
            code_path=str(args.code_path) if args.code_path else None,
        )
        registry.register(program)
        print(f"Registered program {args.program_id} ({args.name})")
        return

    if args.command == "bulk-register":
        programs = []
        with args.jsonl_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                record = json.loads(line)
                programs.append(
                    Program(
                        program_id=record["program_id"],
                        name=record.get("name", record["program_id"]),
                        description=record.get("description", ""),
                        importance=int(record.get("importance", 0)),
                        input_channel=record.get("input_channel", ""),
                        output_channel=record.get("output_channel", ""),
                        code_path=record.get("code_path"),
                    )
                )
        registry.bulk_register(programs)
        print(f"Registered {len(programs)} programs from {args.jsonl_path}")
        return

    if args.command == "list":
        programs = registry.list_programs()
        for program in programs:
            print(
                f"{program.program_id}\t{program.name}\timportance={program.importance}\tinput={program.input_channel}\toutput={program.output_channel}\tcode={program.code_path or 'inline'}"
            )
        return

    if args.command == "runs":
        runs = datastore.list_runs(limit=args.limit, program_id=args.program_id)
        for run in runs:
            run_id, program_id, status, output, started_at, finished_at = run
            print(
                f"#{run_id}\tprogram={program_id}\tstatus={status}\tstarted={started_at}\tfinished={finished_at}\toutput={output}"
            )
        return

    if args.command == "run":
        program = registry.get(args.program_id)
        if not program:
            raise SystemExit(f"Program not found: {args.program_id}")
        payload = _load_payload(args.payload)
        output = executor.execute_registered(program, payload)
        print(json.dumps(output, ensure_ascii=False, indent=2, default=str))
        return

    if args.command == "run-inline":
        program = registry.get(args.program_id)
        if not program:
            program = Program(
                program_id=args.program_id,
                name=f"inline-{args.program_id}",
                description="Ad-hoc inline program",
            )
            registry.register(program)
        payload = _load_payload(args.payload)
        output = executor.execute_inline(program, args.code, payload)
        print(json.dumps(output, ensure_ascii=False, indent=2, default=str))
        return

    if args.command == "demo":
        program = Program(
            program_id="demo-echo",
            name="Echo demo (inline)",
            description="Bundled sample to preview the orchestrator",
            importance=5,
            input_channel="demo:in",
            output_channel="demo:out",
            code_path=None,
        )
        registry.register(program)
        payload = {"text": args.text, "count": args.count}
        output = executor.execute_inline(program, ECHO_SAMPLE_CODE, payload)
        print("تم تشغيل العينة بنجاح. الإخراج:")
        print(json.dumps(output, ensure_ascii=False, indent=2, default=str))
        print(
            "\nللاستمرار بالاستكشاف، راجع السجل عبر: "
            f"python -m app.monolith runs --program-id {program.program_id} --db {args.db}"
        )
        return

    if args.command == "preview-code":
        target = args.file
        if target.is_dir():
            candidate = target / "monolith.py"
            target = candidate if candidate.exists() else target

        if not target.exists():
            raise SystemExit(f"File not found: {target}")

        lines = target.read_text(encoding="utf-8").splitlines()
        start = max(args.start, 1)
        end = args.end or len(lines)
        if start > end:
            raise SystemExit("Start line cannot be greater than end line")

        print(f"عرض الملف: {target} (الأسطر {start}-{end})")
        for idx, line in enumerate(lines[start - 1 : end], start=start):
            print(f"{idx:04d}: {line}")
        return


if __name__ == "__main__":
    main()
