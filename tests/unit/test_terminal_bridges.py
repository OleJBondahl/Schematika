"""Unit tests for terminal_bridges module."""

import csv
import tempfile
from pathlib import Path

from schematika.electrical.utils.terminal_bridges import (
    update_csv_with_internal_connections,
)


class TestUpdateCsvWithInternalConnections:
    """Tests for update_csv_with_internal_connections function."""

    def test_adds_internal_bridge_column(self):
        """Should add 'Internal Bridge' column to CSV."""
        # Create temp CSV with appropriate headers
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, newline=""
        ) as f:
            writer = csv.writer(f)
            writer.writerow(["Terminal", "Device", "Terminal Tag", "Terminal Pin"])
            writer.writerow(["1", "X1", "X1", "1"])
            writer.writerow(["2", "X1", "X1", "2"])
            temp_path = f.name

        try:
            # Terminal X1 pins 1-2 bridged
            internal_connections = {"X1": [(1, 2)]}
            update_csv_with_internal_connections(temp_path, internal_connections)  # ty: ignore[invalid-argument-type]

            # Read back and verify
            with Path(temp_path).open() as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            assert "Internal Bridge" in rows[0].keys()

            # Verify the bridge values
            # Both pins 1 and 2 are in the same bridge group,
            # so they should get index "1"
            assert rows[0]["Internal Bridge"] == "1"
            assert rows[1]["Internal Bridge"] == "1"

        finally:
            Path(temp_path).unlink()

    def test_empty_connections(self):
        """Should handle empty internal_connections dict gracefully."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, newline=""
        ) as f:
            writer = csv.writer(f)
            writer.writerow(["Terminal", "Device", "Terminal Tag", "Terminal Pin"])
            writer.writerow(["1", "X1", "X1", "1"])
            temp_path = f.name

        try:
            update_csv_with_internal_connections(temp_path, {})

            # Read back and verify
            with Path(temp_path).open() as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            assert "Internal Bridge" in rows[0].keys()
            assert rows[0]["Internal Bridge"] == ""

        finally:
            Path(temp_path).unlink()
