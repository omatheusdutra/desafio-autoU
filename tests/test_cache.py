def test_cache_local_set_get(monkeypatch):
    from backend_app.infrastructure import cache

    cache.settings.enable_redis_cache = False
    cache.set_cached("abc", {"x": 1})
    assert cache.get_cached("abc")["x"] == 1

    cache.set_cached_batch("zip", {"y": 2})
    assert cache.get_cached_batch("zip")["y"] == 2


def test_cache_redis_paths(monkeypatch):
    from backend_app.infrastructure import cache

    class FakeRedis:
        def __init__(self):
            self.store = {}

        def get(self, key):
            return self.store.get(key)

        def setex(self, key, ttl, value):
            self.store[key] = value

    fake = FakeRedis()

    def fake_from_url(_url, decode_responses=True):
        return fake

    cache.settings.enable_redis_cache = True
    cache.settings.redis_url = "redis://localhost:6379/0"
    monkeypatch.setattr("backend_app.infrastructure.cache.Redis.from_url", fake_from_url)
    cache._redis_client = None

    cache.set_cached("abc", {"x": 3})
    assert cache.get_cached("abc")["x"] == 3

    cache.set_cached_batch("zip", {"y": 4})
    assert cache.get_cached_batch("zip")["y"] == 4


def test_cache_redis_unavailable(monkeypatch):
    from backend_app.infrastructure import cache

    def raise_err(*_args, **_kwargs):
        raise RuntimeError("redis down")

    cache.settings.enable_redis_cache = True
    cache.settings.redis_url = "redis://localhost:6379/0"
    monkeypatch.setattr("backend_app.infrastructure.cache.Redis.from_url", raise_err)
    cache._redis_client = None

    cache.set_cached("k1", {"x": 1})
    assert cache.get_cached("k1")["x"] == 1


def test_cache_empty_and_redis_read_errors(monkeypatch):
    from backend_app.infrastructure import cache

    cache.settings.enable_redis_cache = True
    cache.settings.redis_url = None
    assert cache.get_cached("") is None

    class BadRedis:
        def get(self, _key):
            raise RuntimeError("fail")

    monkeypatch.setattr("backend_app.infrastructure.cache.Redis.from_url", lambda *_a, **_k: BadRedis())
    cache.settings.redis_url = "redis://localhost:6379/0"
    cache._redis_client = None
    assert cache.get_cached("x") is None
    assert cache.get_cached_batch("y") is None
    assert cache.get_cached_batch("") is None


def test_cache_get_redis_cached_instance(monkeypatch):
    from backend_app.infrastructure import cache

    obj = object()
    cache._redis_client = obj
    assert cache._get_redis() is obj
    cache._redis_client = None


def test_cache_get_redis_none_when_no_url():
    from backend_app.infrastructure import cache

    cache.settings.redis_url = None
    cache._redis_client = None
    assert cache._get_redis() is None


def test_cache_write_exceptions(monkeypatch):
    from backend_app.infrastructure import cache

    class BadRedis:
        def setex(self, *_a, **_k):
            raise RuntimeError("fail")

    cache.settings.enable_redis_cache = True
    cache.settings.redis_url = "redis://localhost:6379/0"
    monkeypatch.setattr("backend_app.infrastructure.cache.Redis.from_url", lambda *_a, **_k: BadRedis())
    cache._redis_client = None

    class BadCache:
        def __setitem__(self, _key, _val):
            raise RuntimeError("fail")

    original_cache = cache._local_cache
    cache._local_cache = BadCache()

    cache.set_cached("x", {"a": 1})
    cache.set_cached_batch("y", {"b": 2})
    cache.set_cached("", {})
    cache.set_cached_batch("", {})
    cache._local_cache = original_cache


def test_cache_local_get_exception(monkeypatch):
    from backend_app.infrastructure import cache

    def bad_get(_key=None):
        raise RuntimeError("fail")

    monkeypatch.setattr(cache._local_cache, "get", bad_get)
    cache.settings.enable_redis_cache = False
    assert cache.get_cached("x") is None
    assert cache.get_cached_batch("y") is None
