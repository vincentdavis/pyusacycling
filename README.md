# usac-velodata

A Python package that scrapes and parses USA Cycling event results from the legacy USA Cycling results page.

## Installation

### Using uv (recommended)

```bash
uv pip install usac-velodata
```

### Using pip

```bash
pip install usac-velodata
```

## Requirements

- Python 3.13 or higher

## Features

- Scrapes USA Cycling event data
- Parses race results
- Extracts event details
- Supports various serialization formats (JSON, CSV)
- Command-line interface for easy usage
- Rate limiting and caching capabilities

## Usage

### Basic Usage

```python
from usac_velodata import USACyclingClient

# Initialize the client
client = USACyclingClient()

# Get event details
event = client.get_event_details("2023-1234")

# Get race results
results = client.get_race_results("2023-1234", "123456")

# Serialize results to JSON
json_data = client.serialize_to_json(results)
```

### Command Line Interface

The package provides a CLI for direct use from the terminal:

```bash
python -m usac_velodata --help
```

Running with uv:

```bash
uv run python -m usac_velodata --help
```

## Development

### Setup Development Environment

```bash
# Clone the repository
git clone https://github.com/yourusername/usac-velodata.git
cd usac-velodata

# Install with development dependencies using uv
uv pip install -e ".[dev]"
```

### Running Tests

```bash
pytest
```

### Code Quality

This project uses Ruff for linting and formatting.

```bash
# Check code with Ruff
uv run ruff check src/

# Auto-fix issues
uv run ruff check --fix src/

# Format code
uv run ruff format src/
```

## License

[Add your license information here]

## Author

- Vincent Davis <vincent@heteroskedastic.net>
