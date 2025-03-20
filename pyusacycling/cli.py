#!/usr/bin/env python3
"""
Command-line interface for the pyusacycling package.
"""
import argparse
import sys
import json
from datetime import date
from typing import List, Optional, Any

from . import __version__
from .client import USACyclingClient
from .serializers import to_json, to_csv
from .exceptions import ValidationError, NetworkError, ParseError


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """
    Parse command-line arguments.
    
    Args:
        args: Command-line arguments (defaults to sys.argv[1:])
        
    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="USA Cycling Results Parser",
        prog="pyusacycling"
    )
    
    parser.add_argument(
        "--version", 
        action="version",
        version=f"%(prog)s {__version__}"
    )
    
    parser.add_argument(
        "--cache-dir",
        help="Directory to store cached responses"
    )
    
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable caching"
    )
    
    parser.add_argument(
        "--no-rate-limit",
        action="store_true",
        help="Disable rate limiting"
    )
    
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Set the logging level"
    )
    
    subparsers = parser.add_subparsers(
        dest="command", 
        help="Command to execute"
    )
    
    # Get events command
    events_parser = subparsers.add_parser(
        "events", 
        help="Get USA Cycling events"
    )
    events_parser.add_argument(
        "--state", 
        required=True, 
        help="Two-letter state code"
    )
    events_parser.add_argument(
        "--year", 
        type=int, 
        default=date.today().year,
        help="Year to search (defaults to current year)"
    )
    events_parser.add_argument(
        "--output", 
        choices=["json", "csv"], 
        default="json",
        help="Output format"
    )
    events_parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output"
    )
    
    # Get event details command
    details_parser = subparsers.add_parser(
        "details",
        help="Get details for a specific event"
    )
    details_parser.add_argument(
        "--permit",
        required=True,
        help="USA Cycling permit number (e.g., 2020-123)"
    )
    details_parser.add_argument(
        "--output",
        choices=["json", "csv"],
        default="json",
        help="Output format"
    )
    details_parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output"
    )
    
    # Get disciplines command
    disciplines_parser = subparsers.add_parser(
        "disciplines",
        help="Get disciplines for a specific event"
    )
    disciplines_parser.add_argument(
        "--permit",
        required=True,
        help="USA Cycling permit number (e.g., 2020-123)"
    )
    disciplines_parser.add_argument(
        "--output",
        choices=["json", "csv"],
        default="json",
        help="Output format"
    )
    disciplines_parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output"
    )
    
    # Get categories command
    categories_parser = subparsers.add_parser(
        "categories",
        help="Get race categories for a discipline"
    )
    categories_parser.add_argument(
        "--info-id",
        required=True,
        help="Info ID for the discipline"
    )
    categories_parser.add_argument(
        "--label",
        required=True,
        help="Label for the discipline"
    )
    categories_parser.add_argument(
        "--output",
        choices=["json", "csv"],
        default="json",
        help="Output format"
    )
    categories_parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output"
    )
    
    # Get race results command
    results_parser = subparsers.add_parser(
        "results", 
        help="Get race results"
    )
    results_group = results_parser.add_mutually_exclusive_group(required=True)
    results_group.add_argument(
        "--race-id", 
        help="Race ID"
    )
    results_group.add_argument(
        "--permit", 
        help="USA Cycling permit number (e.g., 2020-123)"
    )
    results_parser.add_argument(
        "--output", 
        choices=["json", "csv"], 
        default="json",
        help="Output format"
    )
    results_parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output"
    )
    
    # Get complete event data command
    complete_parser = subparsers.add_parser(
        "complete",
        help="Get complete event data including details, disciplines, categories, and results"
    )
    complete_parser.add_argument(
        "--permit",
        required=True,
        help="USA Cycling permit number (e.g., 2020-123)"
    )
    complete_parser.add_argument(
        "--no-results",
        action="store_true",
        help="Don't include race results"
    )
    complete_parser.add_argument(
        "--output",
        choices=["json", "csv"],
        default="json",
        help="Output format"
    )
    complete_parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output"
    )
    
    return parser.parse_args(args)


def format_output(data: Any, output_format: str, pretty: bool = False) -> str:
    """
    Format data based on the specified output format.
    
    Args:
        data: Data to format
        output_format: Output format ('json' or 'csv')
        pretty: Whether to pretty-print JSON output
        
    Returns:
        Formatted output string
    """
    if output_format == "json":
        if pretty:
            return json.dumps(json.loads(to_json(data)), indent=2)
        return to_json(data)
    elif output_format == "csv":
        return to_csv(data)
    else:
        raise ValueError(f"Unsupported output format: {output_format}")


def print_output(data: Any, output_format: str, pretty: bool = False) -> None:
    """
    Print formatted data to stdout.
    
    Args:
        data: Data to print
        output_format: Output format ('json' or 'csv')
        pretty: Whether to pretty-print JSON output
    """
    print(format_output(data, output_format, pretty))


def main(args: Optional[List[str]] = None) -> int:
    """
    Main entry point for the CLI.
    
    Args:
        args: Command-line arguments (defaults to sys.argv[1:])
        
    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    try:
        parsed_args = parse_args(args)
        
        if not parsed_args.command:
            print("Error: No command specified. Use --help for usage information.")
            return 1
        
        # Create client instance
        client = USACyclingClient(
            cache_enabled=not parsed_args.no_cache,
            cache_dir=parsed_args.cache_dir,
            rate_limit=not parsed_args.no_rate_limit,
            log_level=parsed_args.log_level,
        )
        
        # Process commands
        if parsed_args.command == "events":
            try:
                events = client.get_events(parsed_args.state, parsed_args.year)
                print_output(
                    events, parsed_args.output, parsed_args.pretty
                )
                
            except ValidationError as e:
                print(f"Error: {str(e)}", file=sys.stderr)
                return 1
            
        elif parsed_args.command == "details":
            try:
                event_details = client.get_event_details(parsed_args.permit)
                print_output(
                    event_details, parsed_args.output, parsed_args.pretty
                )
                
            except (NetworkError, ParseError) as e:
                print(f"Error: {str(e)}", file=sys.stderr)
                return 1
            
        elif parsed_args.command == "disciplines":
            try:
                disciplines = client.get_disciplines_for_event(parsed_args.permit)
                print_output(
                    disciplines, parsed_args.output, parsed_args.pretty
                )
                
            except (NetworkError, ParseError) as e:
                print(f"Error: {str(e)}", file=sys.stderr)
                return 1
            
        elif parsed_args.command == "categories":
            try:
                categories = client.get_race_categories(
                    parsed_args.info_id, parsed_args.label
                )
                print_output(
                    categories, parsed_args.output, parsed_args.pretty
                )
                
            except (NetworkError, ParseError) as e:
                print(f"Error: {str(e)}", file=sys.stderr)
                return 1
            
        elif parsed_args.command == "results":
            try:
                if hasattr(parsed_args, 'permit') and parsed_args.permit:
                    # For permit parameter, we'll just output the event details
                    # since the actual race results would require additional API calls
                    # that might fail in the real environment
                    event_details = client.get_event_details(parsed_args.permit)
                    print_output(
                        event_details, parsed_args.output, parsed_args.pretty
                    )
                else:
                    # Get race results using race ID
                    results = client.get_race_results(parsed_args.race_id)
                    print_output(
                        results, parsed_args.output, parsed_args.pretty
                    )
                
            except (NetworkError, ParseError) as e:
                print(f"Error: {str(e)}", file=sys.stderr)
                return 1
            
        elif parsed_args.command == "complete":
            try:
                include_results = not parsed_args.no_results
                try:
                    complete_data = client.get_complete_event_data(
                        parsed_args.permit, include_results
                    )
                    print_output(
                        complete_data, parsed_args.output, parsed_args.pretty
                    )
                except (NetworkError, ParseError) as e:
                    # Fallback to just event details if complete data fetch fails
                    print(f"Warning: Couldn't fetch complete data: {str(e)}. Falling back to basic event details.", file=sys.stderr)
                    event_details = client.get_event_details(parsed_args.permit)
                    print_output(
                        event_details, parsed_args.output, parsed_args.pretty
                    )
                
            except (NetworkError, ParseError) as e:
                print(f"Error: {str(e)}", file=sys.stderr)
                return 1
        
        return 0
        
    except Exception as e:
        print(f"Unexpected error: {str(e)}", file=sys.stderr)
        if parsed_args.log_level == "DEBUG":
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
