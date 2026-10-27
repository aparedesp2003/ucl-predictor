import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def football_data_payload() -> dict:
    return json.loads((FIXTURES / "football_data_matches.json").read_text(encoding="utf-8"))


@pytest.fixture
def cl_sample() -> str:
    return (FIXTURES / "cl_sample.txt").read_text(encoding="utf-8")
