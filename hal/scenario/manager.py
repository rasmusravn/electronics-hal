"""
Test scenario management system.

This module provides a high-level interface for managing test scenarios,
including recording, playback, and organization capabilities.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from hal.logging_config import get_logger
from .models import TestScenario
from .recorder import ScenarioRecorder
from .player import ScenarioPlayer, PlaybackResult


class ScenarioManager:
    """Central manager for test scenario operations."""

    def __init__(self, storage_dir: Path, instrument_manager: Any = None):
        """Initialize scenario manager."""
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.instrument_manager = instrument_manager
        self.logger = get_logger(__name__)

        # Initialize recorder and player
        self.recorder = ScenarioRecorder(storage_dir)
        self.player = ScenarioPlayer(storage_dir, instrument_manager)

        self.logger.info(f"Initialized scenario manager with storage: {storage_dir}")

    # Recording operations

    def start_recording(self, scenario_name: str, description: Optional[str] = None,
                       created_by: str = "user") -> str:
        """Start recording a new test scenario."""
        session = self.recorder.start_recording(scenario_name, description, created_by)
        return session.scenario_id

    def stop_recording(self) -> Optional[TestScenario]:
        """Stop current recording session."""
        return self.recorder.stop_recording()

    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self.recorder.is_recording()

    def get_recording_status(self) -> Dict[str, Any]:
        """Get current recording status."""
        return self.recorder.get_recording_status()

    # Playback operations

    def play_scenario(self, scenario_id: str, dry_run: bool = False,
                     continue_on_error: bool = True) -> PlaybackResult:
        """Play scenario by ID."""
        file_path = self._find_scenario_file(scenario_id)
        if not file_path:
            raise FileNotFoundError(f"Scenario {scenario_id} not found")

        return self.player.play_scenario_file(file_path, dry_run, continue_on_error)

    def play_scenario_by_name(self, scenario_name: str, dry_run: bool = False,
                             continue_on_error: bool = True) -> PlaybackResult:
        """Play scenario by name."""
        scenarios = self.list_scenarios()

        matching = [s for s in scenarios if s["summary"]["name"] == scenario_name]
        if not matching:
            raise FileNotFoundError(f"Scenario with name '{scenario_name}' not found")

        if len(matching) > 1:
            self.logger.warning(f"Multiple scenarios found with name '{scenario_name}', using first match")

        file_path = Path(matching[0]["file_path"])
        return self.player.play_scenario_file(file_path, dry_run, continue_on_error)

    def play_scenarios_with_tags(self, tags: List[str], dry_run: bool = False,
                                continue_on_error: bool = True) -> List[PlaybackResult]:
        """Play all scenarios that have any of the specified tags."""
        scenarios = self.list_scenarios()

        matching_files = []
        for scenario in scenarios:
            scenario_tags = scenario["summary"].get("tags", [])
            if any(tag in scenario_tags for tag in tags):
                matching_files.append(Path(scenario["file_path"]))

        if not matching_files:
            self.logger.warning(f"No scenarios found with tags: {tags}")
            return []

        return self.player.play_scenarios_batch(matching_files, dry_run, continue_on_error)

    # Scenario management

    def list_scenarios(self) -> List[Dict[str, Any]]:
        """List all available scenarios."""
        return self.recorder.list_scenarios()

    def get_scenario(self, scenario_id: str) -> Optional[TestScenario]:
        """Get scenario by ID."""
        file_path = self._find_scenario_file(scenario_id)
        if not file_path:
            return None

        return TestScenario.load_from_file(file_path)

    def delete_scenario(self, scenario_id: str) -> bool:
        """Delete scenario by ID."""
        file_path = self._find_scenario_file(scenario_id)
        if not file_path:
            return False

        try:
            file_path.unlink()
            self.logger.info(f"Deleted scenario {scenario_id}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to delete scenario {scenario_id}: {e}")
            return False

    def duplicate_scenario(self, scenario_id: str, new_name: str) -> Optional[str]:
        """Duplicate an existing scenario with a new name."""
        original = self.get_scenario(scenario_id)
        if not original:
            return None

        # Create new scenario with modified metadata
        import uuid
        new_scenario = TestScenario.from_dict(original.to_dict())
        new_scenario.scenario_id = str(uuid.uuid4())
        new_scenario.name = new_name
        new_scenario.version = "1.0"
        new_scenario.execution_count = 0
        new_scenario.last_executed = None

        # Save duplicated scenario
        file_path = self.recorder.save_scenario(new_scenario)
        self.logger.info(f"Duplicated scenario {scenario_id} as {new_scenario.scenario_id}")

        return new_scenario.scenario_id

    def update_scenario_metadata(self, scenario_id: str, **kwargs) -> bool:
        """Update scenario metadata."""
        scenario = self.get_scenario(scenario_id)
        if not scenario:
            return False

        # Update allowed fields
        allowed_fields = ["name", "description", "tags", "version"]
        for field, value in kwargs.items():
            if field in allowed_fields:
                setattr(scenario, field, value)

        # Save updated scenario
        try:
            file_path = self._find_scenario_file(scenario_id)
            scenario.save_to_file(file_path)
            self.logger.info(f"Updated scenario {scenario_id} metadata")
            return True
        except Exception as e:
            self.logger.error(f"Failed to update scenario {scenario_id}: {e}")
            return False

    # Analysis and reporting

    def get_execution_history(self) -> List[Dict[str, Any]]:
        """Get playback execution history."""
        return self.player.get_execution_history()

    def clear_execution_history(self) -> None:
        """Clear playback execution history."""
        self.player.clear_execution_history()

    def analyze_scenario_success_rates(self) -> Dict[str, Any]:
        """Analyze success rates across all scenarios."""
        scenarios = self.list_scenarios()
        history = self.get_execution_history()

        analysis = {
            "total_scenarios": len(scenarios),
            "total_executions": len(history),
            "overall_success_rate": 0.0,
            "scenario_stats": {},
            "recent_trends": []
        }

        if not history:
            return analysis

        # Calculate overall success rate
        successful_executions = sum(1 for h in history if h["success"])
        analysis["overall_success_rate"] = (successful_executions / len(history)) * 100

        # Per-scenario statistics
        scenario_stats = {}
        for execution in history:
            scenario_id = execution["scenario_id"]
            if scenario_id not in scenario_stats:
                scenario_stats[scenario_id] = {
                    "scenario_name": execution["scenario_name"],
                    "executions": 0,
                    "successes": 0,
                    "failures": 0,
                    "avg_duration": 0.0,
                    "durations": []
                }

            stats = scenario_stats[scenario_id]
            stats["executions"] += 1

            if execution["success"]:
                stats["successes"] += 1
            else:
                stats["failures"] += 1

            if execution.get("duration_seconds"):
                stats["durations"].append(execution["duration_seconds"])

        # Calculate averages
        for scenario_id, stats in scenario_stats.items():
            if stats["durations"]:
                stats["avg_duration"] = sum(stats["durations"]) / len(stats["durations"])
            stats["success_rate"] = (stats["successes"] / stats["executions"]) * 100

        analysis["scenario_stats"] = scenario_stats

        return analysis

    def export_scenarios(self, output_dir: Path, format: str = "json") -> List[Path]:
        """Export all scenarios to specified format."""
        output_dir.mkdir(parents=True, exist_ok=True)
        exported_files = []

        scenarios = self.list_scenarios()

        for scenario_info in scenarios:
            scenario = TestScenario.load_from_file(Path(scenario_info["file_path"]))

            if format.lower() == "json":
                output_file = output_dir / f"{scenario.scenario_id}.json"
                scenario.save_to_file(output_file)

            elif format.lower() == "yaml":
                import yaml
                output_file = output_dir / f"{scenario.scenario_id}.yaml"
                with open(output_file, 'w') as f:
                    yaml.dump(scenario.to_dict(), f, default_flow_style=False)

            else:
                raise ValueError(f"Unsupported export format: {format}")

            exported_files.append(output_file)

        self.logger.info(f"Exported {len(exported_files)} scenarios to {output_dir}")
        return exported_files

    def import_scenarios(self, import_dir: Path) -> List[str]:
        """Import scenarios from directory."""
        imported_ids = []

        for file_path in import_dir.glob("*.json"):
            try:
                scenario = TestScenario.load_from_file(file_path)

                # Save to storage directory
                self.recorder.save_scenario(scenario)
                imported_ids.append(scenario.scenario_id)

            except Exception as e:
                self.logger.error(f"Failed to import scenario from {file_path}: {e}")

        self.logger.info(f"Imported {len(imported_ids)} scenarios from {import_dir}")
        return imported_ids

    # Helper methods

    def _find_scenario_file(self, scenario_id: str) -> Optional[Path]:
        """Find scenario file by ID."""
        for file_path in self.storage_dir.glob("*.json"):
            try:
                scenario = TestScenario.load_from_file(file_path)
                if scenario.scenario_id == scenario_id:
                    return file_path
            except Exception:
                continue

        return None

    def get_manager_status(self) -> Dict[str, Any]:
        """Get overall manager status."""
        scenarios = self.list_scenarios()
        history = self.get_execution_history()

        return {
            "storage_dir": str(self.storage_dir),
            "recording": self.is_recording(),
            "total_scenarios": len(scenarios),
            "execution_history_count": len(history),
            "instrument_manager_available": self.instrument_manager is not None
        }