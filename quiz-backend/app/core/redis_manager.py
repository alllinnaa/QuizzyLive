from redis.asyncio import Redis
from app.core.config import settings

_redis: Redis | None = None

async def get_redis() -> Redis:
    """
    Повертає singleton-клієнт Redis. Підтримує TLS через схему rediss://
    та налаштований для керованих хмарних провайдерів (Upstash, Redis Cloud).
    """
    global _redis
    if _redis is None:
        _redis = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            health_check_interval=30,     # періодичний PING для підтримки з'єднання
            socket_timeout=3,             # таймаут на команду
            socket_connect_timeout=3,     # таймаут на конект
            retry_on_timeout=True,
            max_connections=50,
        )
        # Перевірка доступності на старті
        await _redis.ping()
    return _redis

async def close_redis():
    global _redis
    if _redis is not None:
        await _redis.close()
        _redis = None