"""Electronics Hardware Abstraction Layer (HAL) for automated testing."""

# Import key modules for easy access
from . import config_loader as config_loader
from . import database_manager as database_manager
from . import reports as reports

# Version information
__version__ = "0.1.0"
__author__ = "Electronics HAL Team"

# Expose commonly used classes
from .config_loader import load_config as load_config
from .database_manager import DatabaseManager as DatabaseManager
from .reports.report_manager import ReportManager as ReportManager

__all__ = [
    "config_loader",
    "database_manager",
    "reports",
    "load_config",
    "DatabaseManager",
    "ReportManager",
]
