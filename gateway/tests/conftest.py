"""Live subprocess tests are explicit opt-in; normal gateway tests stay isolated and fast."""

import pytest


def pytest_addoption(parser):
    parser.addoption(
        '--run-integration', action='store_true', default=False,
        help='Launch isolated live services, a Temporal dev server, and owned SIGKILL experiments',
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption('--run-integration'):
        return

    skip = pytest.mark.skip(reason='Use --run-integration to launch isolated live subprocesses')
    for item in items:
        if 'integration' in item.keywords:
            item.add_marker(skip)
