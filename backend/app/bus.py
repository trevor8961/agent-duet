"""进程内事件总线：runner 发布、SSE 订阅。

设计取舍：内存态（不落库）——SSE 是"实时性"的载体，历史消费走
raw 文件与 messages 表（持久真相），总线只服务"正在发生的事"。
每个事件带自增 id，支撑 SSE 断线重连的 Last-Event-ID 游标。
"""

import asyncio
import time


class EventBus:
    def __init__(self):
        self._events: dict[int, list[dict]] = {}  # session_id -> 事件列表
        self._conds: dict[int, asyncio.Condition] = {}

    def _cond(self, session_id: int) -> asyncio.Condition:
        if session_id not in self._conds:
            self._conds[session_id] = asyncio.Condition()
        return self._conds[session_id]

    async def publish(self, session_id: int, kind: str, data=None) -> int:
        """发布事件，返回其自增 id。"""
        async with self._cond(session_id):
            events = self._events.setdefault(session_id, [])
            event = {"id": len(events), "kind": kind, "ts": time.time(), "data": data}
            events.append(event)
            self._cond(session_id).notify_all()
            return event["id"]

    async def subscribe(self, session_id: int, cursor: int = -1):
        """从 cursor+1 起持续产出事件，直到 turn_done（含）。

        先补发历史（含 turn_done 则立即结束——重连已完成 turn 的场景），
        再等新事件。生成器由消费方 break/close 终止。
        """
        events = self._events.get(session_id, [])
        idx = cursor + 1
        # 先吐已有的
        while idx < len(events):
            yield events[idx]
            if events[idx]["kind"] == "turn_done":
                return
            idx += 1

        cond = self._cond(session_id)
        while True:
            async with cond:
                await cond.wait_for(lambda: len(self._events.get(session_id, [])) > idx)
                events = self._events[session_id]
                while idx < len(events):
                    yield events[idx]
                    if events[idx]["kind"] == "turn_done":
                        return
                    idx += 1


bus = EventBus()
