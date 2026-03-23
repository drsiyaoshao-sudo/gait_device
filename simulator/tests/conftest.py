"""Add simulator/ to sys.path so imports work without installing a package."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
