"""Each test gets fresh databases and processes; existing local/Compose state is untouched."""

import pytest

from .stack import LiveStack


@pytest.fixture
async def live_stack(tmp_path):
    stack = LiveStack(tmp_path)
    try:
        await stack.start()
        yield stack
    finally:
        stack.close()


@pytest.fixture
async def naive_stack(tmp_path):
    stack = LiveStack(tmp_path, temporal=False)
    try:
        await stack.start()
        yield stack
    finally:
        stack.close()


@pytest.fixture
async def crash_stack(tmp_path):
    stack = LiveStack(tmp_path, barrier=True)
    try:
        await stack.start()
        yield stack
    finally:
        stack.close()
