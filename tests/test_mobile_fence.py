from types import SimpleNamespace

import pytest

import talk_mobile
from talk_dashboard_gateway import DashboardTaskError
from talk_live_config import LiveConfig


def request(session="session-one", profile="default"):
    return SimpleNamespace(headers={"x-talk-mobile": "1", "x-talk-mobile-session": session,
                                    "x-talk-mobile-profile": profile})


def bound(session="session-one", profile="default"):
    return SimpleNamespace(mobile_fence=None,
        attachment=SimpleNamespace(owner=SimpleNamespace(session_id=session)),
        context=SimpleNamespace(profile_name=profile))


def test_existing_binding_keeps_its_fence_when_request_headers_are_removed():
    value = bound()
    talk_mobile.check_bound(request(), value, attach=True)
    assert value.mobile_fence == ("session-one", "default")
    with pytest.raises(DashboardTaskError):
        talk_mobile.check_bound(SimpleNamespace(headers={}), value, config=LiveConfig(auth_mode="api"))


@pytest.mark.parametrize("session,profile", [("other", "default"), ("session-one", "other")])
def test_wrong_chat_or_profile_is_refused_before_activation(session, profile):
    with pytest.raises(DashboardTaskError):
        talk_mobile.check_bound(request(), bound(session, profile), attach=True)


def test_subscription_binding_accepts_only_its_original_context():
    value = bound()
    talk_mobile.check_bound(request(), value, config=LiveConfig(), attach=True)
    talk_mobile.check_bound(request(), value, config=LiveConfig())
    with pytest.raises(DashboardTaskError):
        talk_mobile.check_bound(request("other"), value)


def test_missing_or_unknown_contract_headers_never_attach():
    for headers in ({"x-talk-mobile": "2"}, {"x-talk-mobile": "1"}):
        with pytest.raises((DashboardTaskError, ValueError)):
            talk_mobile.check_bound(SimpleNamespace(headers=headers), bound(), attach=True)


def test_registry_refuses_api_provider_before_negotiation_even_without_headers(tmp_path):
    import asyncio
    from test_live_browser import registry_for
    from test_dashboard_tasks import environment
    fixture = registry_for(environment.__wrapped__(tmp_path))
    fixture.bound.mobile_fence = ("task-a", "default")
    with pytest.raises(DashboardTaskError):
        asyncio.run(fixture.registry.create(fixture.request, {**fixture.context, "sdp": "v=0"}))
    assert fixture.observed == []
    assert fixture.registry.bindings == {}


def test_direct_join_rejects_different_task_before_gateway_join():
    with pytest.raises(DashboardTaskError):
        talk_mobile.check_task(request(), {"session_id": "other", "profile": "default"})


def test_readiness_requires_real_history_store_and_linked_dispatch_support(tmp_path):
    from test_dashboard_tasks import environment
    manager, req, _, _ = environment.__wrapped__(tmp_path)
    talk_mobile.verify_host(req, manager)
    from dataclasses import replace
    changed = replace(manager.resolve_context(req), store_id="different-store")
    manager.resolve_context = lambda request: changed
    with pytest.raises(DashboardTaskError):
        talk_mobile.verify_host(req, manager)


def test_mobile_readiness_refuses_a_host_without_task_context(monkeypatch):
    import asyncio
    from test_dashboard_api import api, FakeRequest
    monkeypatch.setattr(api, "_require_dashboard_auth", lambda request: None)
    monkeypatch.setattr(api.talk_live_config, "resolve_live_config", lambda: LiveConfig())
    monkeypatch.setattr(api.talk_dashboard_tasks, "context_support", lambda: {"supported": False})
    with pytest.raises(api.HTTPException) as failure:
        asyncio.run(api.mobile_status(FakeRequest()))
    assert failure.value.status_code == 503


def test_mobile_uses_verified_host_context_without_copying_native_credentials(monkeypatch):
    from test_dashboard_api import api, FakeRequest
    req = FakeRequest(headers={"x-talk-mobile": "1", "x-talk-mobile-session": "task-a",
                               "x-talk-mobile-profile": "default"})
    req.state = SimpleNamespace(hosted_http_authenticated=True)
    observed = []
    monkeypatch.setattr(api.talk_dashboard_tasks, "resolve_context",
                        lambda request, profile: observed.append(profile))
    monkeypatch.setattr(api, "_require_dashboard_auth", lambda request: pytest.fail("native secret bridge used"))
    monkeypatch.setattr(api, "_resolve_voice_mode", lambda: "live")
    monkeypatch.setattr(api.talk_live_config, "resolve_live_config", lambda: LiveConfig())
    api.require_dashboard_auth(req)
    assert observed == ["default"]


def test_mobile_host_refusal_is_not_replaced_by_legacy_auth(monkeypatch):
    from test_dashboard_api import api, FakeRequest
    req = FakeRequest(headers={"x-talk-mobile": "1", "x-talk-mobile-session": "task-a",
                               "x-talk-mobile-profile": "default"})
    req.state = SimpleNamespace(hosted_http_authenticated=True)
    def refuse(request, profile):
        raise DashboardTaskError("context_denied", 403)
    monkeypatch.setattr(api.talk_dashboard_tasks, "resolve_context", refuse)
    monkeypatch.setattr(api, "_require_dashboard_auth", lambda request: pytest.fail("auth fallback used"))
    with pytest.raises(api.HTTPException) as denied:
        api.require_dashboard_auth(req)
    assert denied.value.status_code == 403


def test_mobile_descriptor_supports_android_snake_case_decoder(monkeypatch):
    import asyncio
    from test_dashboard_api import api, FakeRequest
    monkeypatch.setattr(api, "require_dashboard_auth", lambda request: None)
    monkeypatch.setattr(api.talk_live_config, "resolve_live_config", lambda: LiveConfig())
    monkeypatch.setattr(api.talk_dashboard_tasks, "context_support", lambda: {"supported": True})
    monkeypatch.setattr(api.talk_mobile, "verify_host", lambda request, manager: None)
    monkeypatch.setattr(api, "_resolve_voice_mode", lambda: "live")
    monkeypatch.setattr(api.talk_live_config, "resolve_live_auth",
                        lambda **kwargs: SimpleNamespace(source="codex-app-server"))
    descriptor = asyncio.run(api.mobile_status(FakeRequest()))
    assert descriptor["existingChatOnly"] is True
    assert descriptor.get("existing_chat_only") is True
    assert descriptor["auth"] == "subscription"
