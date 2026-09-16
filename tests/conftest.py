# -*- coding: utf-8 -*-
"""
Pytest Configuration & Fixtures
"""
import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: mark test as requiring external services (e.g. Weaviate)"
    )

