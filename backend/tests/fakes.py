from __future__ import annotations

from collections.abc import Awaitable, Callable


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)

    def first(self):
        return self._rows[0] if self._rows else None


class FakeAsyncSession:
    def __init__(self, execute_handlers: list[Callable[[object], Awaitable[FakeResult] | FakeResult] | FakeResult]):
        self._execute_handlers = list(execute_handlers)

    async def execute(self, stmt):
        if not self._execute_handlers:
            raise AssertionError("Unexpected execute() call in fake session")

        handler = self._execute_handlers.pop(0)
        if callable(handler):
            result = handler(stmt)
        else:
            result = handler

        if hasattr(result, "__await__"):
            result = await result
        return result
