"""Tests for the simple.py module"""
import importlib.resources

from . import data
from mousebender import simple

def test_simple_index_basic():
    index_html = importlib.resources.read_text(data, "simple.index.html")
    index = simple.parse_package_index(index_html)
    assert "numpy" in index
    assert index["numpy"] == "/simple/numpy/"
