"""Pytest fixtures for integration tests against Postgres and MinIO."""

import pytest

from tests.fixtures.bootstrap_db import bootstrap_database


@pytest.fixture(scope="module")
def seeded_database(integration_env):
    from netpulse.config import get_settings

    settings = get_settings()
    bootstrap_database(settings.postgres_host, settings.postgres_port)
    yield settings
