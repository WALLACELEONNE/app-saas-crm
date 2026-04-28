"""
In-memory async Event Bus (RabbitMQ/Kafka abstraction).
Used for: domain events, mobile sync feed, integration outbox.
"""
import asyncio
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Callable, Awaitable
import logging

log = logging.getLogger("events")


class EventBus:
    def __init__(self, buffer_size: int = 1000) -> None:
        self._subs: dict[str, list[Callable[[dict], Awaitable[None]]]] = defaultdict(list)
        self._loop: asyncio.AbstractEventLoop | None = None
        self.history: deque = deque(maxlen=buffer_size)

    def start(self) -> None:
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = None

    def stop(self) -> None:
        self._loop = None

    def subscribe(self, topic: str, handler: Callable[[dict], Awaitable[None]]) -> None:
        self._subs[topic].append(handler)

    def publish(self, topic: str, payload: dict) -> None:
        evt = {
            "topic": topic,
            "payload": payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.history.append(evt)
        if not self._loop:
            return
        for h in self._subs.get(topic, []) + self._subs.get("*", []):
            try:
                self._loop.create_task(h(evt))
            except Exception as e:  # pragma: no cover
                log.error("event handler error: %s", e)


event_bus = EventBus()
