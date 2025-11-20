from dataclasses import dataclass
from typing import Optional


@dataclass
class Program:
    """Representation of a subprogram managed by the orchestrator."""

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
