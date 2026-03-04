"""Pytest configuration and shared fixtures."""

import os

# Set dummy env vars before any app module is imported
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test-dummy")
os.environ.setdefault("RAKUTEN_APP_ID", "dummy_app_id")
os.environ.setdefault("RAKUTEN_ACCESS_KEY", "dummy_access_key")
