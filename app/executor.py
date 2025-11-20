import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

from .datastore import DataStore
from .models import Program


class ProgramExecutor:
    """Executes registered subprograms and records their output."""

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
