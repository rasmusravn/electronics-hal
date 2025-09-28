# Electronics Hardware Abstraction Layer (HAL)

A modern hardware test ecosystem with comprehensive infrastructure for automated testing of electronic devices.

## Features

- **Configuration Management**: Type-safe configuration with Pydantic
- **Hardware Abstraction Layer**: Instrument-agnostic test development
- **Centralized Logging**: Structured logging with test run correlation
- **Data Persistence**: SQLite-based test result storage
- **Automated Reporting**: Dynamic HTML/PDF report generation

## Quick Start

### Installation

```bash
# Install dependencies with uv
uv sync

# Or with pip
pip install -e .
```

### Configuration

1. Copy `config/config.yml.example` to `config/config.yml`
2. Update instrument addresses and paths for your setup
3. Run tests: `pytest`

## Project Structure

```
electronics-hal/
├── hal/                    # Hardware abstraction layer
│   ├── interfaces.py       # Abstract instrument interfaces
│   ├── visa_instrument.py  # VISA communication backend
│   └── drivers/           # Concrete instrument drivers
├── config/                # Configuration files
├── tests/                 # Test suite
├── templates/             # Report templates
├── reports/               # Generated reports
└── logs/                  # Log files
```

## Development

Format code: `ruff format`
Lint code: `ruff check`
Type check: `mypy hal tests`
Run tests: `pytest`