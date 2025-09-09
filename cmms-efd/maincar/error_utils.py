import asyncio
import functools

def safe_execution(retries=3, delay=1.5):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(1, retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    print(f"[RETRY] Attempt {attempt} failed: {e}")
                    if attempt < retries:
                        await asyncio.sleep(delay)
            print(f"[ERROR] All {retries} retries failed for {func.__name__}")
            return None
        return wrapper
    return decorator
