from typing import Iterable, List

from .datastore import DataStore
from .models import Program


class ProgramRegistry:
    """Manages registration and lookup of subprogram definitions."""

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
