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
