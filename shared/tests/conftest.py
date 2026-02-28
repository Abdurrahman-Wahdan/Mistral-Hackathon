"""
Pytest configuration for AI tests.

Adds the ai/ directory to Python path so shared modules can be imported.
"""

import sys
from pathlib import Path
import pytest

# Add ai/ directory to Python path for shared module imports
ai_root = Path(__file__).resolve().parents[2]
if str(ai_root) not in sys.path:
    sys.path.insert(0, str(ai_root))


# Configure pytest-asyncio to use function-scoped event loops
# This ensures each test gets a fresh event loop and fixtures clean up properly
@pytest.fixture(scope="session")
def event_loop_policy():
    import asyncio
    return asyncio.get_event_loop_policy()


def pytest_configure(config):
    """Configure pytest-asyncio event loop scope."""
    config.option.asyncio_mode = "auto"
