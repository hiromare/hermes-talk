"""Existing-chat restrictions for the Android subscription voice surface."""
from __future__ import annotations

from urllib.parse import unquote

try:
    from .talk_dashboard_gateway import DashboardTaskError
    from .talk_passive import HistoryError, identifier, session_id
except ImportError:
    from talk_dashboard_gateway import DashboardTaskError
    from talk_passive import HistoryError, identifier, session_id


def requested_fence(request):
    headers = getattr(request, "headers", {})
    version = headers.get("x-talk-mobile")
    if version is None:
        return None
    if version != "1":
        raise DashboardTaskError("invalid_event", 400)
    selected = unquote(headers.get("x-talk-mobile-session", ""))
    profile = unquote(headers.get("x-talk-mobile-profile", ""))
    try:
        return session_id(selected), identifier(profile)
    except HistoryError as exc:
        raise DashboardTaskError("invalid_event", 400) from exc


def check_config(config):
    if config.auth_mode != "subscription":
        raise DashboardTaskError("context_denied", 403)


def check_bound(request, bound, *, config=None, attach=False):
    requested = requested_fence(request)
    existing = getattr(bound, "mobile_fence", None)
    fence = existing or requested
    if fence is None:
        return
    if requested is not None and requested != fence:
        raise DashboardTaskError("context_denied", 403)
    actual = (bound.attachment.owner.session_id, bound.context.profile_name)
    if actual != fence:
        raise DashboardTaskError("context_denied", 403)
    if config is not None:
        check_config(config)
    if attach:
        bound.mobile_fence = fence


def check_task(request, task):
    fence = requested_fence(request)
    if fence is not None and (task.get("session_id"), task.get("profile")) != fence:
        raise DashboardTaskError("context_denied", 403)
