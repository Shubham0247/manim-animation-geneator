"""Interface definitions for Manim execution (SOLID: Interface Segregation)."""

from abc import ABC, abstractmethod
from core.models import ManimCode, ManimExecutionResult


class IManimExecutor(ABC):
    """Abstract interface for Manim code execution."""
    
    @abstractmethod
    def execute(self, code: ManimCode) -> ManimExecutionResult:
        """
        Execute Manim code and return the result.
        
        Args:
            code: The Manim code to execute
            
        Returns:
            Execution result with success status and video path
        """
        pass
