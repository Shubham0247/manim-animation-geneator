from abc import ABC, abstractmethod
from core.models import ManimCode, ManimExecutionResult


class IManimExecutor(ABC):
    @abstractmethod
    def execute(self, code: ManimCode) -> ManimExecutionResult:
        """Run Manim code and return execution output."""
        pass
