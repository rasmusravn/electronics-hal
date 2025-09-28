"""Base classes for report generators."""

from abc import ABC, abstractmethod
from pathlib import Path

from .models import ReportData


class ReportGenerator(ABC):
    """Base class for all report generators."""

    def __init__(self, output_dir: Path):
        """
        Initialize report generator.

        Args:
            output_dir: Directory where reports will be saved
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    def generate(self, report_data: ReportData, filename: str) -> Path:
        """
        Generate a report from the provided data.

        Args:
            report_data: Complete report data
            filename: Base filename (without extension)

        Returns:
            Path to the generated report file
        """
        pass

    @property
    @abstractmethod
    def file_extension(self) -> str:
        """File extension for this report type."""
        pass

    def get_output_path(self, filename: str) -> Path:
        """Get the full output path for a report file."""
        return self.output_dir / f"{filename}.{self.file_extension}"
