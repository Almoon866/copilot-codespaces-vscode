import argparse
import json
from pathlib import Path
from typing import Any

from .datastore import DataStore
from .executor import ProgramExecutor
from .models import Program
from .registry import ProgramRegistry


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Orchestrator for managing and executing a large set of subprograms",
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
        "demo", help="Initialize, register, and execute the bundled echo sample"
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
        default=Path(__file__).parent / "monolith.py",
        help="مسار ملف الكود المراد عرضه (افتراضيًا الملف الموحّد)",
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
            # Ensure the program exists in the registry so run history can be recorded
            # without violating foreign key constraints.
            registry.register(program)
        payload = _load_payload(args.payload)
        output = executor.execute_inline(program, args.code, payload)
        print(json.dumps(output, ensure_ascii=False, indent=2, default=str))
        return

    if args.command == "demo":
        program = Program(
            program_id="demo-echo",
            name="Echo demo",
            description="Bundled sample to preview the orchestrator",
            importance=5,
            input_channel="demo:in",
            output_channel="demo:out",
            code_path=str(Path(__file__).parent / "samples" / "echo.py"),
        )

        registry.register(program)
        payload = {"text": args.text, "count": args.count}
        output = executor.execute_registered(program, payload)
        print("تم تشغيل العينة بنجاح. الإخراج:")
        print(json.dumps(output, ensure_ascii=False, indent=2, default=str))
        print(
            "\nللاستمرار بالاستكشاف، راجع السجل عبر: "
            f"python -m app.cli runs --program-id {program.program_id} --db {args.db}"
        )
        return

    if args.command == "preview-code":
        target = args.file
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
