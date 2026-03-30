import asyncio

_semaphore: asyncio.Semaphore | None = None


def get_semaphore() -> asyncio.Semaphore:

    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(3)
    return _semaphore
