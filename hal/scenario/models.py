"""
Data models for test scenario recording and playback.

This module defines the core data structures for representing test scenarios,
steps, actions, and validation rules.
"""

import json
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, validator


class ActionType(str, Enum):
    """Types of actions that can be recorded in a test scenario."""

    # Instrument Control
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    CONFIGURE = "configure"
    MEASURE = "measure"
    SET_OUTPUT = "set_output"
    GET_STATUS = "get_status"

    # Test Flow
    START_TEST = "start_test"
    END_TEST = "end_test"
    VALIDATE = "validate"
    WAIT = "wait"
    LOG = "log"

    # System Operations
    SYSTEM_CONFIG = "system_config"
    CALIBRATE = "calibrate"
    RESET = "reset"


class ValidationRule(BaseModel):
    """Validation rule for test step verification."""

    name: str = Field(..., description="Validation rule name")
    parameter: str = Field(..., description="Parameter to validate")
    operator: str = Field(..., description="Comparison operator (eq, ne, gt, lt, ge, le, in, contains)")
    expected_value: Any = Field(..., description="Expected value for comparison")
    tolerance: Optional[float] = Field(default=None, description="Tolerance for numeric comparisons")
    description: Optional[str] = Field(default=None, description="Human-readable description")

    @validator('operator')
    def validate_operator(cls, v):
        valid_operators = ['eq', 'ne', 'gt', 'lt', 'ge', 'le', 'in', 'contains', 'regex']
        if v not in valid_operators:
            raise ValueError(f"Operator must be one of {valid_operators}")
        return v

    def validate_value(self, actual_value: Any) -> bool:
        """Validate actual value against this rule."""
        try:
            if self.operator == 'eq':
                if isinstance(self.expected_value, (int, float)) and self.tolerance:
                    return abs(actual_value - self.expected_value) <= self.tolerance
                return actual_value == self.expected_value

            elif self.operator == 'ne':
                return actual_value != self.expected_value

            elif self.operator == 'gt':
                return actual_value > self.expected_value

            elif self.operator == 'lt':
                return actual_value < self.expected_value

            elif self.operator == 'ge':
                return actual_value >= self.expected_value

            elif self.operator == 'le':
                return actual_value <= self.expected_value

            elif self.operator == 'in':
                return actual_value in self.expected_value

            elif self.operator == 'contains':
                return self.expected_value in str(actual_value)

            elif self.operator == 'regex':
                import re
                return bool(re.search(self.expected_value, str(actual_value)))

            return False

        except Exception:
            return False

    def get_description(self) -> str:
        """Get human-readable description of the validation rule."""
        if self.description:
            return self.description

        op_desc = {
            'eq': 'equals',
            'ne': 'not equals',
            'gt': 'greater than',
            'lt': 'less than',
            'ge': 'greater than or equal to',
            'le': 'less than or equal to',
            'in': 'is in',
            'contains': 'contains',
            'regex': 'matches pattern'
        }

        desc = f"{self.parameter} {op_desc.get(self.operator, self.operator)} {self.expected_value}"
        if self.tolerance:
            desc += f" (±{self.tolerance})"

        return desc


class TestStep(BaseModel):
    """Individual step in a test scenario."""

    step_id: str = Field(..., description="Unique step identifier")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Step execution timestamp")
    action_type: ActionType = Field(..., description="Type of action performed")
    instrument_id: Optional[str] = Field(default=None, description="Target instrument identifier")
    command: Optional[str] = Field(default=None, description="Command or method name")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Action parameters")
    expected_result: Optional[Any] = Field(default=None, description="Expected result")
    actual_result: Optional[Any] = Field(default=None, description="Actual result (recorded)")
    duration_ms: Optional[float] = Field(default=None, description="Execution duration in milliseconds")
    success: bool = Field(default=True, description="Step execution success")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")
    validations: List[ValidationRule] = Field(default_factory=list, description="Validation rules")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    def add_validation(self, name: str, parameter: str, operator: str,
                      expected_value: Any, tolerance: Optional[float] = None) -> None:
        """Add a validation rule to this step."""
        validation = ValidationRule(
            name=name,
            parameter=parameter,
            operator=operator,
            expected_value=expected_value,
            tolerance=tolerance
        )
        self.validations.append(validation)

    def validate_result(self, result: Any) -> List[Dict[str, Any]]:
        """Validate result against all validation rules."""
        validation_results = []

        for rule in self.validations:
            is_valid = rule.validate_value(result)
            validation_results.append({
                "rule_name": rule.name,
                "description": rule.get_description(),
                "passed": is_valid,
                "actual_value": result,
                "expected_value": rule.expected_value
            })

        return validation_results

    def to_dict(self) -> Dict[str, Any]:
        """Convert step to dictionary for serialization."""
        return {
            "step_id": self.step_id,
            "timestamp": self.timestamp.isoformat(),
            "action_type": self.action_type.value,
            "instrument_id": self.instrument_id,
            "command": self.command,
            "parameters": self.parameters,
            "expected_result": self.expected_result,
            "actual_result": self.actual_result,
            "duration_ms": self.duration_ms,
            "success": self.success,
            "error_message": self.error_message,
            "validations": [v.dict() for v in self.validations],
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TestStep":
        """Create step from dictionary."""
        # Convert validations
        validations = []
        for v_data in data.get("validations", []):
            validations.append(ValidationRule(**v_data))

        data["validations"] = validations
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        data["action_type"] = ActionType(data["action_type"])

        return cls(**data)


class TestScenario(BaseModel):
    """Complete test scenario with metadata and steps."""

    scenario_id: str = Field(..., description="Unique scenario identifier")
    name: str = Field(..., description="Human-readable scenario name")
    description: Optional[str] = Field(default=None, description="Scenario description")
    version: str = Field(default="1.0", description="Scenario version")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    created_by: str = Field(default="system", description="Creator identifier")
    tags: List[str] = Field(default_factory=list, description="Scenario tags")

    # Execution metadata
    total_duration_ms: Optional[float] = Field(default=None, description="Total execution duration")
    success_rate: Optional[float] = Field(default=None, description="Success rate percentage")
    last_executed: Optional[datetime] = Field(default=None, description="Last execution timestamp")
    execution_count: int = Field(default=0, description="Number of times executed")

    # Test configuration
    instruments_required: List[str] = Field(default_factory=list, description="Required instruments")
    setup_requirements: Dict[str, Any] = Field(default_factory=dict, description="Setup requirements")
    environment_variables: Dict[str, str] = Field(default_factory=dict, description="Environment variables")

    # Test steps
    steps: List[TestStep] = Field(default_factory=list, description="Ordered test steps")

    # Validation
    global_validations: List[ValidationRule] = Field(default_factory=list, description="Global validation rules")

    @validator('name')
    def validate_name(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError("Scenario name cannot be empty")
        return v.strip()

    def add_step(self, step: TestStep) -> None:
        """Add a test step to the scenario."""
        self.steps.append(step)

    def get_step(self, step_id: str) -> Optional[TestStep]:
        """Get step by ID."""
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None

    def remove_step(self, step_id: str) -> bool:
        """Remove step by ID."""
        for i, step in enumerate(self.steps):
            if step.step_id == step_id:
                del self.steps[i]
                return True
        return False

    def get_duration(self) -> timedelta:
        """Get total scenario duration."""
        if self.total_duration_ms:
            return timedelta(milliseconds=self.total_duration_ms)

        total_ms = sum(step.duration_ms or 0 for step in self.steps)
        return timedelta(milliseconds=total_ms)

    def get_success_rate(self) -> float:
        """Calculate success rate based on steps."""
        if not self.steps:
            return 0.0

        successful_steps = sum(1 for step in self.steps if step.success)
        return (successful_steps / len(self.steps)) * 100

    def get_instruments_used(self) -> List[str]:
        """Get list of unique instruments used in scenario."""
        instruments = set()
        for step in self.steps:
            if step.instrument_id:
                instruments.add(step.instrument_id)
        return list(instruments)

    def validate_requirements(self, available_instruments: List[str]) -> List[str]:
        """Validate that required instruments are available."""
        missing = []
        for required in self.instruments_required:
            if required not in available_instruments:
                missing.append(required)
        return missing

    def to_dict(self) -> Dict[str, Any]:
        """Convert scenario to dictionary for serialization."""
        return {
            "scenario_id": self.scenario_id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "tags": self.tags,
            "total_duration_ms": self.total_duration_ms,
            "success_rate": self.success_rate,
            "last_executed": self.last_executed.isoformat() if self.last_executed else None,
            "execution_count": self.execution_count,
            "instruments_required": self.instruments_required,
            "setup_requirements": self.setup_requirements,
            "environment_variables": self.environment_variables,
            "steps": [step.to_dict() for step in self.steps],
            "global_validations": [v.dict() for v in self.global_validations]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TestScenario":
        """Create scenario from dictionary."""
        # Convert steps
        steps = []
        for step_data in data.get("steps", []):
            steps.append(TestStep.from_dict(step_data))

        # Convert global validations
        global_validations = []
        for v_data in data.get("global_validations", []):
            global_validations.append(ValidationRule(**v_data))

        data["steps"] = steps
        data["global_validations"] = global_validations
        data["created_at"] = datetime.fromisoformat(data["created_at"])

        if data.get("last_executed"):
            data["last_executed"] = datetime.fromisoformat(data["last_executed"])

        return cls(**data)

    def save_to_file(self, file_path: Path) -> None:
        """Save scenario to JSON file."""
        with open(file_path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2, default=str)

    @classmethod
    def load_from_file(cls, file_path: Path) -> "TestScenario":
        """Load scenario from JSON file."""
        with open(file_path, 'r') as f:
            data = json.load(f)
        return cls.from_dict(data)

    def get_summary(self) -> Dict[str, Any]:
        """Get scenario summary information."""
        return {
            "scenario_id": self.scenario_id,
            "name": self.name,
            "version": self.version,
            "total_steps": len(self.steps),
            "success_rate": self.get_success_rate(),
            "duration": str(self.get_duration()),
            "instruments_required": len(self.instruments_required),
            "execution_count": self.execution_count,
            "last_executed": self.last_executed.isoformat() if self.last_executed else None,
            "tags": self.tags
        }