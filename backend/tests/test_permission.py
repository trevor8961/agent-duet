"""事中授权状态机单测（不需要 SDK——直接测我们的回调/解析/resolve 层）。"""

import asyncio
import json

import pytest

from app.sdk_runner import resolve_permission, translate_permission_mode


async def test_translate_modes():
    assert translate_permission_mode("guided") == "default"
    assert translate_permission_mode("readonly") == "dontAsk"
    assert translate_permission_mode("autonomous") == "acceptEdits"
    assert translate_permission_mode("plan") == "plan"
    assert translate_permission_mode("unknown") == "default"  # 未知档位安全兜底


async def test_resolve_permission_allow():
    """场景：权限请求挂起，用户点批准。期望：决议为 allow。"""
    from app import sdk_runner as sr

    rid = "req-test-allow"
    event = asyncio.Event()
    sr._pending[rid] = {"event": event, "decision": None}

    async def waiter():
        await event.wait()
        return sr._pending[rid]["decision"]

    w = asyncio.create_task(waiter())
    await asyncio.sleep(0.05)
    assert resolve_permission(rid, "allow") is True
    assert await asyncio.wait_for(w, timeout=1) == "allow"


async def test_resolve_permission_deny():
    from app import sdk_runner as sr

    rid = "req-test-deny"
    event = asyncio.Event()
    sr._pending[rid] = {"event": event, "decision": None}
    w = asyncio.create_task(event.wait())
    assert resolve_permission(rid, "deny") is True
    await asyncio.wait_for(w, timeout=1)
    assert sr._pending[rid]["decision"] == "deny"


async def test_resolve_unknown_or_double():
    """场景：无效 request_id / 重复处理。期望：返回 False（不崩溃）。"""
    assert resolve_permission("nonexistent", "allow") is False

    from app import sdk_runner as sr

    rid = "req-test-double"
    event = asyncio.Event()
    sr._pending[rid] = {"event": event, "decision": None}
    assert resolve_permission(rid, "allow") is True
    assert resolve_permission(rid, "allow") is False  # 单次消费，后到返回已处理


async def test_resolve_invalid_decision():
    from app import sdk_runner as sr

    rid = "req-test-invalid"
    sr._pending[rid] = {"event": asyncio.Event(), "decision": None}
    assert resolve_permission(rid, "maybe") is False
