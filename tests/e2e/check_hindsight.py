"""End-to-end checks against the running hindsight image (tests/run-e2e.sh).

Runs in the test client container, which reaches hindsight over a network
without internet access and knows the tenant key only as a test value.

    check_hindsight.py store     health, refusal without key, retain, recall, MCP
    check_hindsight.py restored  recall of what `store` retained, after a restart
    check_hindsight.py open      a service started without a tenant key runs open
    check_hindsight.py control-plane       the web interface with its login
    check_hindsight.py control-plane-open  the web interface without a login
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
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


def page(url, cookie=None, method="GET", body=None):
    """Status, body text and Set-Cookie of one request to the control plane,
    without following redirects."""
    headers = {"Content-Type": "application/json", "Accept": "text/html,application/json"}
    if cookie:
        headers["Cookie"] = cookie
    data = json.dumps(body).encode() if body is not None else None
    opener = urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(urllib.request.Request(url, data=data, headers=headers, method=method), timeout=60) as response:
            return response.status, response.read().decode(), response.headers.get("Set-Cookie", "")
    except urllib.error.HTTPError as error:
        text = error.read().decode()
        cookie = error.headers.get("Set-Cookie", "")
        error.close()
        return error.code, text, cookie


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


def location(url, cookie=None):
    """The target of the redirect the control plane answers a page with."""
    headers = {"Accept": "text/html"}
    if cookie:
        headers["Cookie"] = cookie
    opener = urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(urllib.request.Request(url, headers=headers), timeout=60) as response:
            return response.status, ""
    except urllib.error.HTTPError as error:
        target = error.headers.get("Location", "")
        error.close()
        return error.code, target


def rendered(url, cookie=None):
    """Status and body of a page after the redirects of the application: the
    root of the control plane sends the browser on to its start page."""
    host = urllib.parse.urlsplit(url).netloc
    for _ in range(5):
        status, target = location(url, cookie)
        if status not in (301, 302, 303, 307, 308):
            break
        url = urllib.parse.urljoin(url, target)
        # a redirect to another host, such as the bind address 0.0.0.0, leaves
        # the browser stranded
        if urllib.parse.urlsplit(url).netloc != host:
            return status, f"redirect to another host: {target}", url
    status, text, _ = page(url, cookie=cookie)
    return status, text, url


def control_plane():
    """The web interface with a login, in front of the service with the key."""
    base = os.environ["CONTROL_PLANE_URL"].rstrip("/")
    status, target = location(base + "/")
    check("control_plane_sends_to_login_without_session",
          status in (302, 303, 307, 308) and "/login" in target, f"status {status}, location {target}")

    status, _, _ = page(base + "/api/banks")
    check("control_plane_api_refuses_without_session", status == 401, f"status {status}")

    status, _, cookie = page(base + "/api/auth/login", method="POST", body={"key": "a-wrong-key"})
    check("control_plane_refuses_wrong_access_key", status == 401 and not cookie, f"status {status}")

    status, text, cookie = page(base + "/api/auth/login", method="POST",
                                body={"key": os.environ["HINDSIGHT_TEST_ACCESS_KEY"]})
    session = cookie.split(";", 1)[0]
    check("control_plane_login_with_access_key", status == 200 and session, f"status {status}: {text[:300]}")

    status, text, _ = page(base + "/api/banks", cookie=session)
    check("control_plane_lists_the_banks_with_the_tenant_key", status == 200 and f'"{BANK}"' in text,
          f"status {status}: {text[:300]}")

    status, text, url = rendered(base + "/", cookie=session)
    check("control_plane_page_renders_after_login",
          status == 200 and "<html" in text.lower() and "/login" not in url, f"status {status} at {url}: {text[:300]}")


def control_plane_open():
    """The web interface without a login, in front of the open service."""
    base = os.environ["CONTROL_PLANE_URL"].rstrip("/")
    status, text, url = rendered(base + "/")
    check("control_plane_without_access_key_runs_open",
          status == 200 and "<html" in text.lower() and "/login" not in url, f"status {status} at {url}: {text[:300]}")
    status, text, _ = page(base + "/api/banks")
    check("control_plane_open_lists_the_banks", status == 200 and '"banks"' in text, f"status {status}: {text[:300]}")


def main():
    phase = sys.argv[1]
    {"store": store, "restored": restored, "open": open_service,
     "control-plane": control_plane, "control-plane-open": control_plane_open}[phase]()
    print(f"==> {phase}: {PASSED} passed, {FAILED} failed", flush=True)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
