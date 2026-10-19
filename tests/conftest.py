import pytest

@pytest.fixture(autouse=True)
def allow_custom_integration(enable_custom_integrations):
    yield
