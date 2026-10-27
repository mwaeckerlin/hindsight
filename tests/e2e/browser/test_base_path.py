"""The control plane in Chromium: below the base path /hindsight, behind Traefik
with PathPrefix(`/hindsight`) and without StripPrefix, and at the root without
a base path. Both containers carry the access key and reach the service with
the tenant key, which holds the bank `e2e` from the earlier phases."""
from urllib.parse import urlparse

import requests
from playwright.sync_api import Page

from conftest import ACCESS_KEY, BANK, PREFIX, PROXY_URL, ROOT_URL

# every root-absolute URL the rendered document names, in any element
ROOT_ABSOLUTE_URLS = """() => [...document.querySelectorAll('[src],[href],[action]')]
    .flatMap(element => ['src', 'href', 'action'].map(name => element.getAttribute(name)))
    .filter(value => value && value.startsWith('/') && !value.startsWith('//'))"""


def log_in(page: Page, origin, base):
    """Open the control plane, log in on its login page with the access key,
    and return the login path and every request and response of the page."""
    requested = []
    responses = {}
    page.on("request", lambda request: requested.append(request.url))
    page.on("response", lambda response: responses.__setitem__(response.url, response.status))
    page.goto(origin + base + "/")
    page.wait_for_url(lambda url: urlparse(url).path.endswith("/login"))
    login = urlparse(page.url).path
    page.fill("#access-key", ACCESS_KEY)
    page.click("button[type=submit]")
    page.wait_for_url(lambda url: not urlparse(url).path.endswith("/login"))
    page.wait_for_load_state("networkidle")
    return login, requested, responses


def web(urls):
    return [url for url in urls if urlparse(url).scheme in ("http", "https")]


def banks(page: Page, base):
    """The bank list as the page's own session reads it from the API."""
    return page.evaluate(f"fetch('{base}/api/banks').then(response => response.text())")


def test_bare_base_path_reaches_the_login():
    response = requests.get(PROXY_URL + PREFIX, allow_redirects=False, timeout=10)
    assert response.status_code in (302, 303, 307, 308), response.status_code
    assert urlparse(response.headers["Location"]).path == PREFIX + "/login"


def test_api_below_base_path_refuses_without_session():
    assert requests.get(PROXY_URL + PREFIX + "/api/banks", timeout=10).status_code == 401


def test_login_and_page_below_base_path(page: Page):
    login, _, _ = log_in(page, PROXY_URL, PREFIX)
    assert login == PREFIX + "/login"
    path = urlparse(page.url).path
    assert path == PREFIX or path.startswith(PREFIX + "/"), page.url
    assert f'"{BANK}"' in banks(page, PREFIX)


def test_no_request_leaves_the_base_path(page: Page):
    _, requested, _ = log_in(page, PROXY_URL, PREFIX)
    proxy = urlparse(PROXY_URL).netloc
    assert requested, "the page made no request"
    outside = [url for url in web(requested)
               if urlparse(url).netloc != proxy
               or not (urlparse(url).path == PREFIX or urlparse(url).path.startswith(PREFIX + "/"))]
    assert not outside, f"requests left {PREFIX}: {outside}"


def test_assets_and_api_answer_below_base_path(page: Page):
    _, _, responses = log_in(page, PROXY_URL, PREFIX)
    assets = {url: status for url, status in responses.items() if urlparse(url).path.startswith(PREFIX + "/_next/static/")}
    assert assets, "no bundle was loaded below the base path"
    failed = {url: status for url, status in assets.items() if status != 200}
    assert not failed, f"assets failed: {failed}"
    api = {url: status for url, status in responses.items() if urlparse(url).path.startswith(PREFIX + "/api/")}
    assert 200 in api.values(), f"no API call of the page answered 200: {api}"


def test_document_names_no_url_outside_the_base_path(page: Page):
    log_in(page, PROXY_URL, PREFIX)
    outside = [url for url in page.evaluate(ROOT_ABSOLUTE_URLS) if not (url == PREFIX or url.startswith(PREFIX + "/"))]
    assert not outside, f"the page names URLs outside {PREFIX}: {outside}"


def test_control_plane_without_base_path_serves_at_the_root(page: Page):
    login, requested, responses = log_in(page, ROOT_URL, "")
    assert login == "/login"
    root = urlparse(ROOT_URL).netloc
    own = [url for url in web(requested) if urlparse(url).netloc == root]
    assert own, "the page made no request to its own server"
    prefixed = [url for url in own if urlparse(url).path.startswith(PREFIX + "/")]
    assert not prefixed, f"the root build asked for {PREFIX}: {prefixed}"
    assets = {url: status for url, status in responses.items() if urlparse(url).path.startswith("/_next/static/")}
    assert assets and set(assets.values()) == {200}, f"assets at the root: {assets}"
    assert f'"{BANK}"' in banks(page, "")
