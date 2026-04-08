"""
Tipos de runtime e estados canônicos para execuções e tarefas.
"""

from typing import Literal


ExecutionState = Literal[
    "planned",
    "running",
    "waiting_human",
    "waiting_job",
    "resumed",
    "completed",
    "failed",
    "awaiting_clarification",
]


TaskKind = Literal["tool", "specialist", "skill", "system"]
