"""Parser classes for the USA Cycling Results Parser package."""

import contextlib
import json
import os
import re
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any, ClassVar
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup

from .exceptions import NetworkError, ParseError
from .utils import logger


class BaseParser:
    """Base parser class with common functionality for USA Cycling data parsing.

    This base class provides methods for fetching and parsing HTML/JSON content
    from USA Cycling's legacy website and API endpoints. It handles:
    - HTTP requests with proper error handling
    - Rate limiting
    - Caching responses
    - HTML parsing with BeautifulSoup
    - Common parsing utilities
    """

    BASE_URL = "https://legacy.usacycling.org"
    RESULTS_URL = urljoin(BASE_URL, "/results/")
    API_URL = urljoin(BASE_URL, "/results/index.php")

    DEFAULT_HEADERS: ClassVar[dict[str, str]] = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/91.0.4472.124 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Cookie": "usacsess=jrkj6v50ftsqkboga0rgbqgrs1",
    }

    def __init__(
        self,
        cache_enabled: bool = True,
        cache_dir: str | None = None,
        rate_limit: bool = True,
        max_retries: int = 3,
        retry_delay: float = 2.0,
    ):
        """Initialize the base parser.

        Args:
            cache_enabled: Whether to enable response caching
            cache_dir: Directory to store cached responses (defaults to ~/.usac_velodata/cache)
            rate_limit: Whether to enable rate limiting
            max_retries: Maximum number of retries for failed requests
            retry_delay: Delay between retries in seconds

        """
        self.cache_enabled = cache_enabled
        self.cache_dir = cache_dir or os.path.expanduser("~/.usac_velodata/cache")
        self.rate_limit = rate_limit
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        # Create cache directory if it doesn't exist
        if self.cache_enabled:
            os.makedirs(self.cache_dir, exist_ok=True)

        self.session = requests.Session()
        self.session.headers.update(self.DEFAULT_HEADERS)

    def _get_cache_path(self, url: str) -> Path:
        """Get the cache file path for a URL.

        Args:
            url: The URL to cache

        Returns:
            Path object for the cache file

        """
        # Create a safe filename from the URL
        safe_url = quote(url, safe="")
        return Path(self.cache_dir) / f"{safe_url}.json"

    def _get_from_cache(self, url: str) -> dict[str, Any] | None:
        """Get response from cache.

        Args:
            url: The URL to get from cache

        Returns:
            The cached response, or None if not in cache or expired

        """
        if not self.cache_enabled:
            return None

        cache_path = self._get_cache_path(url)

        if not cache_path.exists():
            return None

        try:
            with open(cache_path, encoding="utf-8") as f:
                cache_data = json.load(f)

            # Check if cache is expired
            if "expires_at" in cache_data:
                # Handle both timestamp (float) and ISO format (str) for backward compatibility
                if isinstance(cache_data["expires_at"], str):
                    try:
                        expires_at = datetime.fromisoformat(cache_data["expires_at"])
                    except (ValueError, TypeError):
                        # If string format is invalid, treat as expired
                        return None
                else:
                    # If it's a timestamp (float)
                    expires_at = datetime.fromtimestamp(float(cache_data["expires_at"]))

                if datetime.now() > expires_at:
                    return None

            return cache_data
        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
            logger.warning(f"Error reading cache for {url}: {e!s}")
            return None

    def _save_to_cache(self, url: str, data: dict[str, Any], expire_seconds: int = 3600) -> None:
        """Save response to cache.

        Args:
            url: The URL being cached
            data: The response data to cache
            expire_seconds: Cache expiration time in seconds

        """
        if not self.cache_enabled:
            return

        cache_path = self._get_cache_path(url)

        # Add cache metadata
        cache_data = {
            "url": url,
            "cached_at": datetime.now().isoformat(),
            "expires_at": datetime.now().timestamp() + expire_seconds,  # Store as timestamp for consistency
            "response": data,
        }

        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, indent=2)
        except Exception as e:
            logger.warning(f"Error saving cache for {url}: {e!s}")

    def _fetch_with_retries(
        self,
        url: str,
        method: str = "GET",
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        headers: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> requests.Response:
        """Fetch a URL with retries for failed requests.

        Args:
            url: The URL to fetch
            method: HTTP method (GET, POST, etc.)
            params: URL parameters
            data: Form data
            headers: HTTP headers
            json_data: JSON data for POST requests

        Returns:
            requests.Response object

        Raises:
            NetworkError: If all retries fail

        """
        merged_headers = {**self.DEFAULT_HEADERS}
        if headers:
            merged_headers.update(headers)

        for attempt in range(self.max_retries):
            try:
                response = self.session.request(
                    method=method, url=url, params=params, data=data, headers=merged_headers, json=json_data, timeout=30
                )

                # Check for rate limiting
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After", self.retry_delay * 2)
                    retry_after = float(retry_after) if retry_after.isdigit() else self.retry_delay * 2
                    logger.warning(f"Rate limited, waiting {retry_after} seconds")
                    time.sleep(retry_after)
                    continue

                response.raise_for_status()
                return response

            except requests.RequestException as e:
                logger.warning(f"Request failed (attempt {attempt + 1}/{self.max_retries}): {e!s}")

                if attempt < self.max_retries - 1:
                    # Exponential backoff
                    sleep_time = self.retry_delay * (2**attempt)
                    logger.info(f"Retrying in {sleep_time} seconds...")
                    time.sleep(sleep_time)
                else:
                    logger.error(f"All retries failed for {url}")
                    raise NetworkError(f"Failed to fetch {url} after {self.max_retries} attempts: {e!s}") from e

    def _fetch_content(self, url: str, params: dict[str, Any] | None = None) -> str:
        """Fetch HTML content from a URL.

        Args:
            url: The URL to fetch
            params: Optional URL parameters

        Returns:
            str: The HTML content

        Raises:
            NetworkError: If the request fails

        """
        # Check cache first
        if self.cache_enabled:
            cache_key = url
            if params:
                cache_key += "?" + "&".join(f"{k}={v}" for k, v in params.items())

            cached_data = self._get_from_cache(cache_key)
            if cached_data:
                logger.debug(f"Using cached response for {url}")
                return cached_data["response"]

        # Make the request
        try:
            response = self._fetch_with_retries(url, params=params)

            # Cache the response
            if self.cache_enabled:
                self._save_to_cache(cache_key if params else url, response.text)

            return response.text
        except Exception as e:
            logger.error(f"Failed to fetch {url}: {e!s}")
            raise NetworkError(f"Failed to fetch {url}: {e!s}") from e

    def _fetch_json(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        method: str = "GET",
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Fetch JSON data from a URL.

        Args:
            url: The URL to fetch
            params: Optional URL parameters
            method: HTTP method (GET, POST, etc.)
            data: Form data for POST requests

        Returns:
            Dict: Parsed JSON response

        Raises:
            NetworkError: If the request fails
            ParseError: If the response isn't valid JSON

        """
        # Check cache first
        if self.cache_enabled:
            cache_key = url
            if params:
                cache_key += "?" + "&".join(f"{k}={v}" for k, v in params.items())

            cached_data = self._get_from_cache(cache_key)
            if cached_data:
                logger.debug(f"Using cached response for {url}")
                return cached_data["response"]

        # Make the request
        try:
            response = self._fetch_with_retries(
                url,
                method=method,
                params=params,
                data=data,
                headers={"Accept": "application/json, text/javascript, */*; q=0.01"},
            )

            try:
                json_data = response.json()

                # Cache the response
                if self.cache_enabled:
                    self._save_to_cache(cache_key if params else url, json_data)

                return json_data
            except ValueError as e:
                # Sometimes USAC returns HTML instead of JSON even with application/json header
                if "<html" in response.text.lower():
                    logger.warning(f"Expected JSON but got HTML from {url}")
                    raise ParseError(f"Expected JSON but got HTML from {url}") from e
                else:
                    logger.error(f"Failed to parse JSON from {url}: {e!s}")
                    raise ParseError(f"Failed to parse JSON from {url}: {e!s}") from e

        except Exception as e:
            logger.error(f"Failed to fetch JSON from {url}: {e!s}")
            if isinstance(e, ParseError | NetworkError):
                raise
            else:
                raise NetworkError(f"Failed to fetch JSON from {url}: {e!s}") from e

    def _make_soup(self, html: str) -> BeautifulSoup:
        """Create a BeautifulSoup object from HTML.

        Args:
            html: HTML content

        Returns:
            BeautifulSoup: Parsed HTML

        Raises:
            ParseError: If parsing fails

        """
        try:
            return BeautifulSoup(html, "html.parser")
        except Exception as e:
            logger.error(f"Failed to parse HTML: {e!s}")
            raise ParseError(f"Failed to parse HTML: {e!s}") from e

    def _extract_text(self, element) -> str:
        """Extract text from a BeautifulSoup element, handling None values.

        Args:
            element: BeautifulSoup element or None

        Returns:
            Extracted text or empty string

        """
        if element is None:
            return ""
        if "<" in element.get_text(strip=True):
            try:
                return element.get_text(strip=True).split("<")[0]
            except Exception:
                return element.get_text(strip=True)
        return element.get_text(strip=True)

    def _extract_date(self, date_str: str) -> date | None:
        """Extract date from a string.

        Args:
            date_str: Date string in various formats

        Returns:
            date object or None if parsing fails

        """
        if not date_str:
            return None

        date_formats = [
            "%m/%d/%Y",  # 12/31/2020
            "%Y-%m-%d",  # 2020-12-31
            "%B %d, %Y",  # December 31, 2020
            "%b %d, %Y",  # Dec 31, 2020
        ]

        for date_format in date_formats:
            try:
                return datetime.strptime(date_str.strip(), date_format).date()
            except ValueError:
                continue

        logger.warning(f"Failed to parse date: {date_str}")
        return None

    def _extract_load_info_id(self, onclick_text: str) -> str | None:
        """Extract loadInfoID from an onclick attribute.

        Args:
            onclick_text: The onclick attribute text

        Returns:
            The loadInfoID or None if not found

        """
        if not onclick_text:
            return None

        import re

        match = re.search(r"loadInfoID\((\d+)", onclick_text)
        if match:
            return match.group(1)

        return None

    def _extract_race_id(self, race_element_id: str) -> str | None:
        """Extract race ID from a race element ID.

        Args:
            race_element_id: The race element ID (e.g., 'race_1234567')

        Returns:
            The race ID or None if not found

        """
        if not race_element_id:
            return None

        import re

        match = re.search(r"race_(\d+)", race_element_id)
        if match:
            return match.group(1)

        return None

    def _build_permit_url(self, permit: str) -> str:
        """Build a permit URL from a permit number.

        Args:
            permit: The permit number (e.g., '2020-26')

        Returns:
            Full permit URL

        """
        return f"{self.RESULTS_URL}?permit={permit}"

    def _build_load_info_url(self, info_id: str, label: str) -> str:
        """Build a load info URL from an info ID and label.

        Args:
            info_id: The info ID
            label: The category label

        Returns:
            Full load info URL

        """
        params = {"ajax": 1, "act": "infoid", "info_id": info_id, "label": label}
        query_string = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
        return f"{self.API_URL}?{query_string}"

    def _build_race_results_url(self, race_id: str) -> str:
        """Build a race results URL from a race ID.

        Args:
            race_id: The race ID

        Returns:
            Full race results URL

        """
        return f"{self.API_URL}?ajax=1&act=loadresults&race_id={race_id}"

    def fetch_event_list(self, state: str, year: int) -> str:
        """Fetch event list HTML for a state and year.

        Args:
            state: Two-letter state code
            year: Year to fetch

        Returns:
            HTML content of event list

        """
        url = f"{self.BASE_URL}/results/browse.php"
        params = {"state": state, "race": "", "fyear": year}
        return self._fetch_content(url, params)

    def fetch_permit_page(self, permit: str) -> str:
        """Fetch permit page HTML.

        Args:
            permit: Permit number (e.g., '2020-26')

        Returns:
            HTML content of permit page

        """
        url = self._build_permit_url(permit)
        return self._fetch_content(url)

    def fetch_load_info(self, info_id: str, label: str) -> dict[str, Any]:
        """Fetch load info data.

        Args:
            info_id: The info ID
            label: The category label

        Returns:
            Parsed data from HTML or JSON response

        """
        url = self._build_load_info_url(info_id, label)
        html_content = self._fetch_content(url)
        soup = self._make_soup(html_content)

        # Extract race categories from HTML
        result = {"categories": []}
        race_items = soup.select("li[id^='race_']")
        for item in race_items:
            race_id = self._extract_race_id(item.get("id", ""))
            if race_id:
                category_name = self._extract_text(item.find("a"))
                result["categories"].append({"id": race_id, "name": category_name})
        print('result', result)
        return result

    def fetch_race_results(self, race_id: str) -> dict[str, Any]:
        """Fetch race results data.

        Args:
            race_id: The race ID

        Returns:
            Parsed data from HTML or JSON response

        """
        # For real requests, continue with normal flow
        url = self._build_race_results_url(race_id)

        # Add referer header to mimic browser behavior
        headers = {"Referer": f"{self.RESULTS_URL}?permit=2020-26"}

        # Try to get from cache
        if self.cache_enabled:
            cache_key = url
            cached_data = self._get_from_cache(cache_key)
            if cached_data:
                logger.debug(f"Using cached response for {url}")
                return cached_data["response"]

        try:
            # Make the request with session (which includes cookies)
            response = self._fetch_with_retries(url=url, method="GET", headers=headers)

            html_content = response.text
            logger.debug(f"Response received for {url}, length: {len(html_content)}")

            # Parse JSON response if it looks like JSON
            json_data = None
            if html_content.startswith("{"):
                try:
                    json_data = json.loads(html_content)
                    if "message" in json_data:
                        # Extract HTML from JSON response
                        html_content = json_data["message"]
                    elif "d" in json_data:
                        # Extract HTML from 'd' field in JSON response (older format)
                        html_content = json_data["d"]
                except (json.JSONDecodeError, KeyError):
                    # If not valid JSON, continue with HTML parsing
                    pass

            # Check if response contains "Unauthorized access!"
            if "Unauthorized access!" in html_content:
                logger.warning(f"Received unauthorized access response for {url}")
                logger.debug("Returning empty results as fallback")
                # Return a minimal results object as fallback
                return {"id": race_id, "name": "", "riders": []}

            soup = self._make_soup(html_content)

            # Extract race results from HTML
            result = {"id": race_id, "name": "", "riders": []}

            # Try to find race title
            race_title = soup.select_one("h4.race-title")
            if race_title:
                result["name"] = self._extract_text(race_title)
            else:
                # Try alternate title format
                race_title = soup.select_one("span.race-name")
                if race_title:
                    result["name"] = self._extract_text(race_title)

            # USA Cycling uses div elements with class 'tablerow' for the data rows
            table_rows = soup.select("div.tablerow")
            logger.debug(f"Found {len(table_rows)} rows in race results")

            # If no rows were found, try looking for more traditional table format
            if not table_rows:
                results_table = soup.select_one("table.results-table")
                if results_table:
                    table_headers = [th.text.strip() for th in results_table.select("thead th")]
                    rows = results_table.select("tbody tr")

                    for row in rows:
                        rider_data = {}
                        cells = row.select("td")
                        for i, cell in enumerate(cells):
                            if i < len(table_headers):
                                rider_data[table_headers[i]] = self._extract_text(cell)
                        if rider_data:
                            result["riders"].append(rider_data)
            else:
                # Process the div-based table format
                # First, find all header cells to get column names
                header_cells = soup.select("div.tablecell.header")
                if header_cells:
                    headers = []
                    for cell in header_cells:
                        text = self._extract_text(cell)
                        if text and text != "\u00a0":  # Ignore non-breaking spaces
                            headers.append(text)

                    # Process each row
                    for row in table_rows:
                        if "odd" in row.get("class", []) or "even" in row.get("class", []):
                            rider_data = {}
                            cells = row.select("div.tablecell.results")

                            # Common fields we'll extract (based on position)
                            if len(cells) >= 2:
                                rider_data["place"] = self._extract_text(cells[1])

                            if len(cells) >= 5:
                                # Find the name link
                                name_link = cells[4].select_one("a")
                                rider_data["name"] = (
                                    self._extract_text(name_link) if name_link else self._extract_text(cells[4])
                                )

                            if len(cells) >= 6:
                                # Location (may be city, state)
                                rider_data["location"] = self._extract_text(cells[5])

                            if len(cells) >= 7:
                                # Time
                                rider_data["time"] = self._extract_text(cells[6])

                            if len(cells) >= 9:
                                # License
                                rider_data["license"] = self._extract_text(cells[8])

                            if len(cells) >= 10:
                                # Bib
                                rider_data["bib"] = self._extract_text(cells[9])

                            if len(cells) >= 11:
                                # Team
                                rider_data["team"] = self._extract_text(cells[10])

                            if rider_data:
                                result["riders"].append(rider_data)

            # Cache the response
            if self.cache_enabled:
                self._save_to_cache(url, result)

            return result

        except Exception as e:
            logger.error(f"Failed to fetch race results for {race_id}: {e!s}")
            # Return minimal result on error
            return {"id": race_id, "name": "", "riders": []}


class EventListParser(BaseParser):
    """Parser for event listings by state and year."""

    def parse(self, state: str, year: int) -> list[dict[str, Any]]:
        """Parse event listings for a state and year.

        Args:
            state: Two-letter state code
            year: Year to parse

        Returns:
            List of event dictionaries containing:
                - event_date: Date of the event
                - name: Name of the event
                - permit: Permit number
                - permit_url: URL to the permit page
                - submit_date: Date when results were submitted

        """
        # Fetch the event list HTML
        html = self.fetch_event_list(state, year)

        # Parse HTML with BeautifulSoup
        soup = self._make_soup(html)

        # Find the event table
        events_table = soup.find("table", class_="datatable")
        if not events_table:
            logger.warning(f"No event table found for {state} in {year}")
            return []

        # Find all event rows
        event_rows = events_table.find_all("tr")

        # Skip header rows (first 2 rows)
        if len(event_rows) <= 2:
            logger.warning(f"No event rows found for {state} in {year}")
            return []

        # Parse event rows (skip header rows)
        events = []
        for row in event_rows[2:]:  # Skip the header rows
            cells = row.find_all("td")

            # Skip rows with insufficient cells (there should be at least 4 cells)
            if len(cells) < 4:
                continue

            # Skip empty rows (first cell should be empty)
            if self._extract_text(cells[0]):
                continue

            # Extract event date from second cell
            event_date_str = self._extract_text(cells[1])
            event_date = self._extract_date(event_date_str)

            # Extract event name and permit number from third cell
            event_link = cells[2].find("a")
            if not event_link:
                continue

            event_name = self._extract_text(event_link)
            event_url = event_link.get("href", "")

            # Extract permit number from URL
            permit = ""
            if event_url:
                # The permit URL format is like: /results/?permit=2020-26
                import re

                permit_match = re.search(r"permit=([^&]+)", event_url)
                if permit_match:
                    permit = permit_match.group(1)

            # Make the URL absolute
            if event_url and not event_url.startswith(("http://", "https://")):
                event_url = urljoin(self.BASE_URL, event_url)

            # Extract submit date from fourth cell
            submit_date_str = self._extract_text(cells[3])
            submit_date = self._extract_date(submit_date_str)

            # Create event dictionary
            event = {
                "event_date": event_date,
                "name": event_name,
                "permit": permit,
                "permit_url": event_url,
                "submit_date": submit_date,
            }

            events.append(event)

        return events

    def get_events(self, state: str, year: int) -> list[dict[str, Any]]:
        """Get event listings for a state and year and convert to Event models.

        Args:
            state: Two-letter state code
            year: Year to fetch

        Returns:
            List of event dictionaries

        """
        events_data = self.parse(state, year)

        # Add year to each event
        for event in events_data:
            event["year"] = year
            event["state"] = state

            # Create unique ID from permit number
            if event.get("permit"):
                event["id"] = event["permit"]
            else:
                # If no permit, create an ID from name, date, and state
                name_part = event.get("name", "")[:20].replace(" ", "_").lower()
                date_part = str(event.get("event_date", ""))
                event["id"] = f"{name_part}_{date_part}_{state}"

        return events_data


class EventDetailsParser(BaseParser):
    """Parser for individual event details."""

    def parse(self, permit: str) -> dict[str, Any]:
        """Parse details for an individual event using its permit number.

        Args:
            permit: Permit number (e.g., '2020-26')

        Returns:
            Event details dictionary containing:
                - id: Unique ID (same as permit number)
                - name: Name of the event
                - permit_number: Permit number
                - start_date: Start date of the event
                - end_date: End date of the event
                - location: Location of the event
                - state: State abbreviation
                - disciplines: List of disciplines
                - categories: List of categories
                - year: Year of the event

        """
        # Fetch the permit page HTML
        html = self.fetch_permit_page(permit)

        # Parse HTML with BeautifulSoup
        soup = self._make_soup(html)

        # Extract event details
        event_details = {}

        # Set the ID and permit number
        event_details["id"] = permit
        event_details["permit_number"] = permit

        # Extract the year from the permit number
        year_match = re.match(r"(\d{4})-", permit)
        if year_match:
            event_details["year"] = int(year_match.group(1))
        else:
            # Default to current year if not found
            event_details["year"] = datetime.now().year

        # Extract event name, dates, and location
        event_header = soup.select_one("#pgcontent h3")
        if event_header and event_header.get_text(strip=True):
            header_text = event_header.get_text(strip=True)

            # Split by <br/> tags to get separate lines
            header_lines = []
            if event_header.contents:
                current_line = ""
                for content in event_header.contents:
                    if content.name == "br":
                        header_lines.append(current_line.strip())
                        current_line = ""
                    else:
                        current_line += str(content)
                if current_line.strip():
                    header_lines.append(current_line.strip())

            # If we couldn't extract using br tags, try splitting by newlines
            if not header_lines:
                header_lines = [line.strip() for line in header_text.split("\n") if line.strip()]

            if len(header_lines) >= 1:
                event_details["name"] = header_lines[0]

            if len(header_lines) >= 2:
                location_parts = header_lines[1].split(",")
                if len(location_parts) >= 2:
                    event_details["location"] = location_parts[0].strip()
                    state_part = location_parts[1].strip()
                    # Extract the state abbreviation (2 letters)
                    state_match = re.search(r"\b([A-Z]{2})\b", state_part)
                    if state_match:
                        event_details["state"] = state_match.group(1)
                    else:
                        event_details["state"] = ""

            if len(header_lines) >= 3:
                # Parse date range: "Dec 2, 2020 - Dec 30, 2020"
                date_text = header_lines[2]
                dates = re.findall(r"([A-Za-z]+ \d+, \d{4})", date_text)

                if len(dates) >= 1:
                    start_date = self._extract_date(dates[0])
                    if start_date:
                        event_details["start_date"] = start_date

                if len(dates) >= 2:
                    end_date = self._extract_date(dates[1])
                    if end_date:
                        event_details["end_date"] = end_date
                elif "start_date" in event_details:
                    # If only one date is found, use it for both start and end dates
                    event_details["end_date"] = event_details["start_date"]

        # Extract disciplines
        disciplines = list()
        discipline_links = soup.select('a[onclick^="loadInfoID"]')

        for link in discipline_links:
            # Extract info_id and date from onclick attribute
            onclick = link.get("onclick", "")
            info_id_match = re.search(r"loadInfoID\((\d+)", onclick)
            date_match = re.search(r"\d{2}/\d{2}/\d{4}", onclick)

            discipline_text = self._extract_text(link)
            if discipline_text:
                # Clean up the discipline name (remove date if present)
                clean_discipline = re.sub(r"\s+\d{2}/\d{2}/\d{4}$", "", discipline_text)

                # Extract race date if present
                clean_race_date = date_match.group(0) if date_match else ""

                # Extract load_info_id
                load_info_id = info_id_match.group(1) if info_id_match else ""

                disciplines.append(
                    {"load_info_id": load_info_id, "discipline": clean_discipline, "race_date": clean_race_date}
                )

        event_details["disciplines"] = list(disciplines)

        # Extract categories - will require additional API calls in a future implementation
        # For now, we'll leave it as an empty list
        event_details["categories"] = []
        race_result_parser = RaceResultsParser()
        for discipline in disciplines:
            event_details["categories"].append(
                {
                    "load_info_id": discipline.get("load_info_id", ""),
                    "categories": race_result_parser.parse_race_categories(discipline.get("load_info_id", ""), ""),
                }
            )
        # Set default values for fields that might not be extracted
        defaults = {
            "name": f"Event {permit}",
            "location": "Unknown",
            "state": "",
            "start_date": None,
            "end_date": None,
            "is_usac_sanctioned": True,
            "promoter": None,
            "promoter_email": None,
            "website": None,
            "registration_url": None,
            "description": None,
        }

        # Apply defaults for missing fields
        for key, default_value in defaults.items():
            if key not in event_details:
                event_details[key] = default_value

        return event_details

    def get_event_details(self, permit: str) -> dict[str, Any]:
        """Get event details for a permit and convert to EventDetails model.

        Args:
            permit: Permit number (e.g., '2020-26')

        Returns:
            Event details dictionary

        """
        return self.parse(permit)


class RaceResultsParser(BaseParser):
    """Parser for race results."""

    def parse(self, race_id: str) -> dict[str, Any]:
        """Parse race results for a given race ID.

        Args:
            race_id: ID of the race

        Returns:
            Race results dictionary with:
                - id: Race ID
                - name: Race category name
                - category: Category info dictionary
                - event_id: Event ID (if available)
                - date: Race date (if available)
                - riders: List of rider dictionaries

        """
        # Fetch race results
        race_results_data = self.fetch_race_results(race_id)

        # Initialize race data
        race_data = {"id": race_id, "name": "", "category": {}, "riders": [], "event_id": None, "date": None}

        # Handle the new HTML direct parsing response format
        if "id" in race_results_data and race_results_data["id"] == race_id and "riders" in race_results_data:
            race_data["name"] = race_results_data.get("name", "")
            race_data["riders"] = race_results_data.get("riders", [])

            # Try to extract additional details from the name
            category_name = race_data["name"]
            category = {}

            if category_name:
                # Try to extract gender
                gender_match = re.search(r"\b(Men|Women)\b", category_name)
                if gender_match:
                    category["gender"] = gender_match.group(1)

                # Try to extract category rank
                rank_match = re.search(r"Category\s+([A-Z])", category_name)
                if rank_match:
                    category["category_rank"] = rank_match.group(1)

                # Check for special category types
                if "masters" in category_name.lower():
                    category["category_type"] = "Masters"
                elif "juniors" in category_name.lower():
                    category["category_type"] = "Juniors"

                race_data["category"] = category

            return race_data

        # Handle original JSON response format
        if not isinstance(race_results_data, dict) or "d" not in race_results_data:
            logger.warning(f"Invalid race results data format for race ID {race_id}")
            return race_data

        # Extract HTML content from JSON response
        race_results_html = race_results_data.get("d", "")
        if not race_results_html:
            logger.warning(f"No race results found for race ID {race_id}")
            return race_data

        # Parse HTML
        soup = self._make_soup(race_results_html)

        # Extract race name
        race_name_element = soup.select_one("span.race-name")
        if race_name_element:
            race_data["name"] = self._extract_text(race_name_element)

        # Extract riders
        race_data["riders"] = self._extract_riders(soup)

        return race_data

    def _extract_riders(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        """Extract rider information from BeautifulSoup object.

        Args:
            soup: BeautifulSoup object of race results HTML

        Returns:
            List of rider dictionaries

        """
        riders = []

        # Find all rider rows (table rows with 'odd' or 'even' class)
        rider_rows = soup.select("div.tablerow.odd, div.tablerow.even")

        for row in rider_rows:
            # Get all table cells for this row
            cells = row.select("div.tablecell.results")

            # Skip if we don't have enough cells
            if len(cells) < 6:
                continue

            # Extract rider information
            place = self._extract_text(cells[1])  # Place column
            points = self._extract_text(cells[2])  # Points column

            # Get rider name from the name cell
            name_cell = cells[4]
            name_link = name_cell.select_one("a")
            name = self._extract_text(name_link) if name_link else self._extract_text(name_cell)

            # Extract location (city, state)
            location = self._extract_text(cells[5])
            city = None
            state = None

            if location:
                location_parts = location.split(",")
                if len(location_parts) >= 1:
                    city = location_parts[0].strip()
                if len(location_parts) >= 2:
                    state = location_parts[1].strip()

            # Extract time
            time = self._extract_text(cells[6])

            # Extract license number
            license_num = self._extract_text(cells[8])

            # Extract bib number
            bib = self._extract_text(cells[9])

            # Extract team
            team = self._extract_text(cells[10])

            # Parse place to determine special statuses (DNF, DNS, DQ)
            is_dnf = False
            is_dns = False
            is_dq = False
            place_number = None

            if place:
                place_lower = place.lower()
                is_dnf = "dnf" in place_lower
                is_dns = "dns" in place_lower
                is_dq = "dq" in place_lower or "dsq" in place_lower

                # Try to extract a numeric place
                if not any([is_dnf, is_dns, is_dq]):
                    with contextlib.suppress(ValueError, TypeError):
                        place_number = int(place)

            # Create rider dictionary
            rider = {
                "place": place,
                "place_number": place_number,
                "name": name,
                "city": city,
                "state": state,
                "team": team,
                "license": license_num,
                "bib": bib,
                "time": time,
                "is_dnf": is_dnf,
                "is_dns": is_dns,
                "is_dq": is_dq,
            }

            # Add points if available
            if points:
                try:
                    rider["points"] = int(points)
                except (ValueError, TypeError):
                    rider["points"] = None

            riders.append(rider)

        return riders

    def parse_race_categories(self, info_id: str, label: str) -> list[dict[str, Any]]:
        """Parse race categories from a load_info response.

        Args:
            info_id: The info ID (e.g., '132893')
            label: The category label

        Returns:
            List of race category dictionaries containing:
                - id: Race ID
                - name: Category name
                - info_id: Info ID
                - label: Category label

        """
        # Fetch load info
        load_info_data = self.fetch_load_info(info_id, label)
        # Handle the direct HTML parsing result from fetch_load_info
        if "categories" in load_info_data:
            categories = []
            for cat in load_info_data["categories"]:
                category = {"race_id": cat["id"], "name": cat["name"], "info_id": info_id, "label": label}

                # Parse category details
                gender = None
                age_range = None
                category_rank = None
                category_type = None

                if cat["name"]:
                    # Try to extract gender (Men/Women)
                    gender_match = re.search(r"\b(Men|Women)\b", cat["name"])
                    if gender_match:
                        gender = gender_match.group(1)

                    # Try to extract category rank (A, B, C, D, etc.)
                    rank_match = re.search(r"Category\s+([A-Z])", cat["name"])
                    if rank_match:
                        category_rank = rank_match.group(1)

                    # Check for special category types
                    if "masters" in cat["name"].lower():
                        category_type = "Masters"
                    elif "juniors" in cat["name"].lower():
                        category_type = "Juniors"

                # Add parsed details
                category["gender"] = gender
                category["category_rank"] = category_rank
                category["category_type"] = category_type

                categories.append(category)

            return categories

        # Handle the original JSON response format
        elif "message" in load_info_data:
            html_content = load_info_data.get("message", "")
            soup = self._make_soup(html_content)

            categories = []

            # Extract event details for context
            event_name = ""
            event_elem = soup.select_one(".event-title")
            if event_elem:
                event_name = self._extract_text(event_elem)

            # Find race categories (list items with race_* IDs)
            race_elements = soup.select("li[id^='race_']")

            for race_elem in race_elements:
                # Extract race ID from the element ID
                race_id = self._extract_race_id(race_elem.get("id", ""))
                if not race_id:
                    continue

                # Get category name
                category_link = race_elem.select_one("a")
                category_name = ""
                if category_link:
                    category_name = self._extract_text(category_link)

                # Parse category details
                gender = None
                age_range = None
                category_rank = None
                category_type = None

                if category_name:
                    # Try to extract gender (Men/Women)
                    gender_match = re.search(r"\b(Men|Women)\b", category_name)
                    if gender_match:
                        gender = gender_match.group(1)

                    # Try to extract category rank (A, B, C, D, etc.)
                    rank_match = re.search(r"Category\s+([A-Z])", category_name)
                    if rank_match:
                        category_rank = rank_match.group(1)

                    # Check for special category types
                    if "masters" in category_name.lower():
                        category_type = "Masters"
                    elif "juniors" in category_name.lower():
                        category_type = "Juniors"

                # Try to extract age range (e.g., 40+, 19-29, etc.)
                age_match = re.search(r"(\d+(?:\s*[-+]\s*\d*)?)", category_name)
                if age_match:
                    age_range = age_match.group(1).strip()

                # Create category dictionary
                category = {
                    "id": race_id,
                    "name": category_name,
                    "info_id": info_id,
                    "label": label,
                    "discipline": "",
                    "gender": gender,
                    "category_type": category_type,
                    "age_range": age_range,
                    "category_rank": category_rank,
                    "event_name": event_name,
                    "event_location": "",
                    "event_date_range": "",
                }

                categories.append(category)

        return categories

    def get_race_results(self, race_id: str, category_info: dict[str, Any] | None = None) -> dict[str, Any]:
        """Get race results for a specific race ID with category information.

        Args:
            race_id: ID of the race
            category_info: Optional category information to include

        Returns:
            Complete race result dictionary

        """
        race_results = self.parse(race_id)

        if category_info:
            # Update category information
            race_results["category"].update(category_info)

            # Extract event_id from category_info if available
            if "event_id" in category_info:
                race_results["event_id"] = category_info["event_id"]

            # Extract race date from category_info if available
            if "race_date" in category_info:
                race_results["date"] = category_info["race_date"]

        return race_results
