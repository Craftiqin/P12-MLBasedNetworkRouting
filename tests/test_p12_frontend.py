from urllib.error import HTTPError, URLError
import urllib.request

import streamlit
from streamlit.testing.v1 import AppTest


def test_dashboard_renders_without_credentials_or_api_access(monkeypatch):
    monkeypatch.delenv("P12_IOT_INGEST_TOKEN", raising=False)
    monkeypatch.setattr(streamlit, "secrets", {})

    def unavailable(*args, **kwargs):
        raise URLError("offline test fixture")

    monkeypatch.setattr(urllib.request, "urlopen", unavailable)
    app = AppTest.from_file("app.py").run(timeout=20)

    assert not app.exception
    assert [item.value for item in app.title] == ["P12-IOT LIVE ROUTING MONITOR"]
    assert any("Authentication token missing" in item.value for item in app.warning)


def test_streamlit_secrets_load_and_rejected_token_is_distinguished(monkeypatch):
    monkeypatch.delenv("P12_IOT_INGEST_TOKEN", raising=False)

    def rejected_control(url, *args, **kwargs):
        target = url.full_url if isinstance(url, urllib.request.Request) else str(url)
        if "routing-control" in target:
            raise HTTPError(url, 401, "Unauthorized", {}, None)
        raise URLError("offline test fixture")

    monkeypatch.setattr(urllib.request, "urlopen", rejected_control)
    app = AppTest.from_file("app.py").run(timeout=20)

    assert not app.exception
    assert app.session_state["p12_auth_configured"] is True
    assert any("rejected P12_IOT_INGEST_TOKEN (HTTP 401)" in item.value for item in app.warning)
    assert not any("Authentication token missing" in item.value for item in app.warning)
    assert all("Bearer " not in item.value for item in app.warning)
