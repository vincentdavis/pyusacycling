# USA Cycling Results Parser (pyusacycling)

A Python package that scrapes and parses USA Cycling event results from the legacy USA Cycling results page and API. The package extracts event details, race results, categories, rankings, and historical data, returning structured data in multiple formats.

[![PyPI version](https://img.shields.io/pypi/v/pyusacycling.svg)](https://pypi.org/project/pyusacycling/)
[![Python versions](https://img.shields.io/pypi/pyversions/pyusacycling.svg)](https://pypi.org/project/pyusacycling/)
[![License](https://img.shields.io/pypi/l/pyusacycling.svg)](https://github.com/yourusername/pyusacycling/blob/main/LICENSE)

## 🚀 Features

- **Event Data**: Fetch event lists by state and year from USA Cycling API
- **Result Parsing**: Extract race results from the legacy USA Cycling results page
- **Comprehensive Data**: Get event details, race categories, and rider information
- **Historical Data**: Support for fetching data across multiple years
- **Flexible Output**: Export data in multiple formats (Pydantic models, JSON, CSV)
- **Resilient Fetching**: Built-in retry mechanism and rate limiting
- **Efficient Caching**: Local storage of results to minimize requests
- **Type Safety**: Fully type-annotated API with Pydantic validation

## 📦 Installation

### Standard installation

```bash
pip install pyusacycling
```

### For development

```bash
git clone https://github.com/karthicksakkaravarti/pyusacycling.git
cd pyusacycling
pip install -e ".[dev]"
```

## 🔍 Usage Examples

### Using the Python API

```python
from pyusacycling import USACyclingClient

# Initialize client
client = USACyclingClient()

# Get events for a state and year
events = client.get_events(state="CO", year=2023)

# Get details for an event by permit number
event_details = client.get_event_details(permit="2020-26")

# Get race results for a specific permit
all_result = client.get_complete_event_data(permit="2020-26", include_results=True) 

# Get race results for a specific permit
race_results = client.get_race_results(race_id="1337864")


# Export to JSON
json_data = race_results.json()

# Export to CSV
with open("results.csv", "w") as f:
    f.write(race_results.to_csv())
    
# Configure caching
client = USACyclingClient(
    cache_enabled=True,
    cache_dir="./data/cache",
    cache_expiry=86400  # 24 hours
)

# Using rate limiting
client = USACyclingClient(
    rate_limit=10,  # Max 10 requests per minute
    backoff_factor=2.0  # Exponential backoff factor for retries
)
```

### Using the Command-Line Interface

The package includes a command-line interface for quick access to data:

```bash
# Get events for a state
pyusacycling events --state CA --year 2023 --output json

# Get race results for a permit
pyusacycling results --permit 2023-123 --output csv
```

### Detailed CLI Usage

The `pyusacycling` package can be used directly from the command line:

```bash
python -m pyusacycling [command] [options]
```

Available commands:

- `events`: Fetch events by state and year
- `details`: Get detailed information about a specific event
- `disciplines`: List available disciplines
- `categories`: List available race categories
- `results`: Get race results for a specific event
- `complete`: Get complete event information including results

#### Global Options

- `--version`: Show the version and exit
- `--cache-dir PATH`: Directory to store cached data
- `--no-cache`: Disable caching of results
- `--log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}`: Set logging level

#### Events Command

```bash
python -m pyusacycling events --state CA [--year 2023] [--output {json,csv}] [--pretty]
```

- `--state`: Two-letter state code (required)
- `--year`: Year to search (defaults to current year)
- `--output`: Output format (json or csv)
- `--pretty`: Pretty-print JSON output

#### Results Command

```bash
# Using race ID (detailed results for a specific race)
python -m pyusacycling results --race-id 1337864 [--output {json,csv}] [--pretty]

# Using permit (returns event details)
python -m pyusacycling results --permit 2023-123 [--output {json,csv}] [--pretty]
```

- `--race-id`: Specific race ID for detailed results
- `--permit`: Event permit number (returns event details)
- `--output`: Output format (json or csv)
- `--pretty`: Pretty-print JSON output

#### Complete Command

```bash
python -m pyusacycling complete --permit 2023-123 [--no-results] [--output {json,csv}] [--pretty]
```

- `--permit`: Event permit number (required)
- `--no-results`: Don't include race results
- `--output`: Output format (json or csv)
- `--pretty`: Pretty-print JSON output

> Note: If complete data cannot be fetched (due to network or parsing issues), the command will automatically fall back to returning basic event details.

#### Examples

```bash
# Get events in California for 2023 in CSV format
python -m pyusacycling events --state CA --year 2023 --output csv

# Get detailed information about an event with pretty-printed JSON
python -m pyusacycling details --permit 2023-123 --pretty

# Get race results with caching disabled
python -m pyusacycling results --permit 2023-123 --output json --no-cache

# Get complete event information with debug logging
python -m pyusacycling complete --permit 2023-123 --log-level DEBUG
```

## 📘 API Reference

### Client

```python
USACyclingClient(
    cache_enabled: bool = True,
    cache_dir: Optional[str] = None,
    cache_expiry: int = 86400,
    rate_limit: int = 10,
    backoff_factor: float = 1.0,
    logger: Optional[logging.Logger] = None
)
```

### Methods

| Method | Description |
|--------|-------------|
| `get_events(state, year)` | Get events for a state and year |
| `get_event_details(permit)` | Get details for an event by permit number |
| `get_race_results(permit)` | Get race results for a permit |

### Models

- `Event`: Represents a cycling event
- `RaceCategory`: Represents a race category
- `Rider`: Represents a race participant
- `RaceResult`: Represents race results

## 🏗️ Architecture

The package is structured around these main components:

- **Client**: Main interface for users, coordinates the workflow
- **Parsers**: Extract structured data from HTML and JSON responses
- **Models**: Pydantic models for type-validated data structures
- **Utils**: Helper functions for caching, logging, and rate limiting

## 🛠️ Development

### Setup Development Environment

```bash
pip install -e ".[dev]"
```

### Running Tests

```bash
pytest
```

### Code Style

This project uses Black, isort, and flake8 for code formatting and linting:

```bash
# Format code
black pyusacycling tests
isort pyusacycling tests

# Check code style
flake8 pyusacycling tests
mypy pyusacycling
```

## ❓ Troubleshooting

### Common Issues

- **Rate Limiting**: If you encounter "429 Too Many Requests" errors, reduce your rate_limit setting
- **Parsing Errors**: HTML structure may change; check for updates or submit an issue
- **Missing Results**: Some events may not have results published yet

### Logging

Enable detailed logging for troubleshooting:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

client = USACyclingClient()
```

## 👥 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.


python -m unittest discover -v