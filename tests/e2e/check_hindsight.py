"""End-to-end checks against the running hindsight image (tests/run-e2e.sh).

Runs in the test client container, which reaches hindsight over a network
without internet access and knows the tenant key only as a test value.

    check_hindsight.py store     health, refusal without key, retain, recall, MCP
    check_hindsight.py restored  recall of what `store` retained, after a restart
    check_hindsight.py open      a service started without a tenant key runs open
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

URL = os.environ["HINDSIGHT_URL"].rstrip("/")
KEY = os.environ["HINDSIGHT_TEST_KEY"]
BANK = "e2e"
FACT = "The build host of the family is called saturn."

PASSED = 0
FAILED = 0


def check(name, condition, detail=""):
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  PASS  {name}", flush=True)
    else:
        FAILED += 1
        print(f"  FAIL  {name}: {detail}", flush=True)


def request(method, path, body=None, key=KEY, accept="application/json", timeout=60):
    """Status and body text of one request; HTTP errors are answers, not exceptions."""
    headers = {"Content-Type": "application/json", "Accept": accept}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    data = json.dumps(body).encode() if body is not None else None
    call = urllib.request.Request(URL + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(call, timeout=timeout) as response:
            return response.status, response.read().decode()
    except urllib.error.HTTPError as error:
        text = error.read().decode()
        error.close()
        return error.code, text


def recall_finds(word, attempts=45):
    """Recall until the retained fact is found; retain works in the background."""
    text = ""
    for _ in range(attempts):
        status, text = request("POST", f"/v1/default/banks/{BANK}/memories/recall",
                               {"query": "What is the build host called?", "max_tokens": 1024})
        if status == 200 and word in text:
            return True, text
        time.sleep(2)
    return False, text[:300]


def store():
    status, _ = request("GET", "/health", key=None)
    check("health_answers_without_key", status == 200, f"status {status}")

    status, _ = request("GET", "/v1/default/banks", key=None)
    check("api_refuses_request_without_key", status in (401, 403), f"status {status}")

    status, _ = request("GET", "/v1/default/banks", key="a-wrong-key")
    check("api_refuses_wrong_key", status in (401, 403), f"status {status}")

    status, text = request("POST", f"/v1/default/banks/{BANK}/memories",
                           {"items": [{"content": FACT, "document_id": "e2e"}], "async": False},
                           timeout=300)
    check("retain_with_key", status == 200, f"status {status}: {text[:300]}")

    found, text = recall_finds("saturn")
    check("recall_with_key_finds_the_fact", found, text)

    mcp = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
           "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                      "clientInfo": {"name": "hindsight-e2e", "version": "1"}}}
    stream = "application/json, text/event-stream"
    status, text = request("POST", f"/mcp/{BANK}/", mcp, accept=stream)
    check("mcp_endpoint_answers_with_key", status == 200 and "serverInfo" in text, f"status {status}: {text[:300]}")

    status, _ = request("POST", f"/mcp/{BANK}/", mcp, key=None, accept=stream)
    check("mcp_endpoint_refuses_without_key", status in (401, 403), f"status {status}")


def restored():
    found, text = recall_finds("saturn")
    check("memory_survives_a_restart", found, text)


def open_service():
    """The service without a tenant key answers without a key."""
    status, text = request("GET", "/v1/default/banks", key=None)
    check("without_tenant_key_the_api_runs_open", status == 200, f"status {status}: {text[:300]}")


def main():
    phase = sys.argv[1]
    {"store": store, "restored": restored, "open": open_service}[phase]()
    print(f"==> {phase}: {PASSED} passed, {FAILED} failed", flush=True)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
