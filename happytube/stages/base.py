"""Base class for all processing stages."""

from abc import ABC, abstractmethod
from pathlib import Path
from datetime import date
from typing import Dict, Any


class Stage(ABC):
    """Base class for all processing stages."""

    def __init__(self, stage_name: str, base_path: Path = Path("stages")):
        """Initialize a Stage.

        Args:
            stage_name: Name of the stage (e.g., 'fetch', 'assess', 'enhance')
            base_path: Base path for all stage directories
        """
        self.stage_name = stage_name
        self.stage_path = base_path / stage_name

    def get_stage_dir(self, target_date: date) -> Path:
        """Get stage directory for a specific date.

        Args:
            target_date: Date for which to get the stage directory

        Returns:
            Path to the stage directory for the given date
        """
        return self.stage_path / target_date.strftime("%Y-%m-%d")

    def ensure_stage_dir(self, target_date: date) -> Path:
        """Create stage directory if it doesn't exist.

        Args:
            target_date: Date for which to create the stage directory

        Returns:
            Path to the created/existing stage directory
        """
        stage_dir = self.get_stage_dir(target_date)
        stage_dir.mkdir(parents=True, exist_ok=True)
        return stage_dir

    @abstractmethod
    async def run(self, target_date: date) -> Dict[str, Any]:
        """Run the stage processing.

        Args:
            target_date: Date for which to run the stage

        Returns:
            Dictionary containing stage execution statistics and results
        """
        pass
