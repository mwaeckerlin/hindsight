"""Shared settings of the browser suite: addresses, the access key, readiness."""
import os
import time

import pytest
import requests

PROXY_URL = os.environ.get("PROXY_URL", "http://proxy:8080").rstrip("/")
PREFIX = os.environ.get("PREFIX", "/hindsight")
ROOT_URL = os.environ.get("ROOT_URL", "http://control-plane:9999").rstrip("/")
ACCESS_KEY = os.environ["HINDSIGHT_TEST_ACCESS_KEY"]
BANK = "e2e"


def wait_for(url, timeout=120):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            status = requests.get(url, timeout=3).status_code
            if status == 200:
                return
            last = f"status {status}"
        except requests.RequestException as error:
            last = error
        time.sleep(1)
    raise TimeoutError(f"{url} did not answer 200 within {timeout}s: {last}")


@pytest.fixture(scope="session", autouse=True)
def services_ready():
    # /api/health is public, also behind the login
    wait_for(PROXY_URL + PREFIX + "/api/health")
    wait_for(ROOT_URL + "/api/health")
