"""Pytest configuration for backend tests."""

import sys
from pathlib import Path

# Add backend directory to sys.path so tests can import modules
sys.path.insert(0, str(Path(__file__).parent.parent))
