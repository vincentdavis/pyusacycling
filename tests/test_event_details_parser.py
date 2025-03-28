"""Tests for the EventDetailsParser class."""

import os
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from usac_velodata.exceptions import NetworkError
from usac_velodata.parser import EventDetailsParser


class TestEventDetailsParser(unittest.TestCase):
    """Tests for the EventDetailsParser class."""

    def setUp(self):
        """Set up test environment."""
        self.parser = EventDetailsParser(cache_enabled=False)

        # Path to test fixture
        samples_dir = Path(os.path.dirname(os.path.dirname(__file__))) / "samples"
        fixture_path = samples_dir / "permit_pages" / "2020-26.html"

        # Sample event details HTML
        if fixture_path.exists():
            with open(fixture_path, encoding="utf-8") as f:
                self.sample_html = f.read()
        else:
            # Create a minimal event details HTML for tests if fixture doesn't exist
            self.sample_html = """
            <div id="pgcontent" class="onecol">
                <div id='resultsmain'>
                    <h3>USA Cycling December VRL<br/>
                    Colorado Springs, CO<br/>
                    Dec 2, 2020 - Dec 30, 2020</h3>
                    <div class='tablerow'>
                        <div class='tablecell'>
                            <a href='javascript:void(0)' onclick="loadInfoID(132893,
                            'Cross Country Ultra Endurance 12/02/2020')">
                                Cross Country Ultra Endurance
                            </a>
                        </div>
                        <div class='tablecell'>12/02/2020</div>
                    </div>
                    <div class='tablerow'>
                        <div class='tablecell'>
                            <a href='javascript:void(0)' onclick="loadInfoID(132897,
                            'Cross Country Ultra Endurance 12/09/2020')">
                                Cross Country Ultra Endurance
                            </a>
                        </div>
                        <div class='tablecell'>12/09/2020</div>
                    </div>
                </div>
            </div>
            """

    @mock.patch("usac_velodata.parser.BaseParser.fetch_permit_page")
    def test_parse(self, mock_fetch):
        """Test parsing event details from permit page."""
        # Mock the fetch_permit_page method to return our sample HTML
        mock_fetch.return_value = self.sample_html
        
        # Parse the event details
        event_details = self.parser.parse("2020-26")
        
        # Verify event details were parsed correctly
        self.assertIsInstance(event_details, dict)
        
        # Check required fields
        self.assertEqual(event_details["id"], "2020-26")
        self.assertEqual(event_details["permit_number"], "2020-26")
        self.assertEqual(event_details["year"], 2020)
        
        # Check name and location
        self.assertEqual(event_details["name"], "USA Cycling December VRL")
        self.assertEqual(event_details["location"], "Colorado Springs")
        self.assertEqual(event_details["state"], "CO")
        
        # Check dates
        self.assertEqual(event_details["start_date"], date(2020, 12, 2))
        self.assertEqual(event_details["end_date"], date(2020, 12, 30))
        
        # Check disciplines
        disciplines = [d["discipline"] for d in event_details["disciplines"]]
        self.assertIn("Cross Country Ultra Endurance", disciplines)

        # Verify required fields are present
        required_fields = [
            "id",
            "name",
            "permit_number",
            "start_date",
            "end_date",
            "location",
            "state",
            "year",
            "disciplines",
            "categories",
            "is_usac_sanctioned",
            "promoter",
            "promoter_email",
            "website",
            "registration_url",
            "description",
        ]
        for field in required_fields:
            self.assertIn(field, event_details)

    @mock.patch("usac_velodata.parser.BaseParser.fetch_permit_page")
    def test_parse_minimal_html(self, mock_fetch):
        """Test parsing event details with minimal HTML."""
        # Create a minimal HTML that only has the permit number
        minimal_html = "<html><body>Permit 2020-26</body></html>"
        mock_fetch.return_value = minimal_html

        # Parse the event details
        event_details = self.parser.parse("2020-26")

        # Verify basic required fields are present with default values
        self.assertEqual(event_details["id"], "2020-26")
        self.assertEqual(event_details["permit_number"], "2020-26")
        self.assertEqual(event_details["year"], 2020)
        self.assertEqual(event_details["name"], "Event 2020-26")
        self.assertEqual(event_details["location"], "Unknown")
        self.assertEqual(event_details["disciplines"], [])

    @mock.patch("usac_velodata.parser.BaseParser.fetch_permit_page")
    def test_get_event_details(self, mock_fetch):
        """Test getting event details through the higher-level method."""
        # Mock the fetch_permit_page method
        mock_fetch.return_value = self.sample_html

        # Get the event details
        event_details = self.parser.get_event_details("2020-26")

        # Verify event details were returned correctly
        self.assertIsInstance(event_details, dict)
        self.assertEqual(event_details["id"], "2020-26")
        self.assertEqual(event_details["name"], "USA Cycling December VRL")

    @mock.patch("usac_velodata.parser.BaseParser.fetch_permit_page")
    def test_network_error(self, mock_fetch):
        """Test handling of network errors."""
        # Mock the fetch_permit_page method to raise a NetworkError
        mock_fetch.side_effect = NetworkError("Failed to fetch permit page")

        # Verify NetworkError is raised
        with self.assertRaises(NetworkError):
            self.parser.parse("2020-26")


if __name__ == "__main__":
    unittest.main()
