"""Pytest configuration and test isolation fixtures."""

import os
import pytest


@pytest.fixture(autouse=True)
def default_offline_test_env():
    """
    Ensure all unit tests run offline using MockLLMClient by default,
    preventing unintended live Anthropic API calls during test runs.
    Specific tests testing Anthropic configuration can explicitly override this.
    """
    original_provider = os.environ.get("FACTUAL_LLM_PROVIDER")
    os.environ["FACTUAL_LLM_PROVIDER"] = "mock"
    yield
    if original_provider is not None:
        os.environ["FACTUAL_LLM_PROVIDER"] = original_provider
    else:
        os.environ.pop("FACTUAL_LLM_PROVIDER", None)
