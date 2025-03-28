"""Main entry point for the pyusacycling package when executed as a module."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
