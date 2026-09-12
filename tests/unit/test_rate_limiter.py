from core.rate_limit import check_send_rate_limits


async def test_allows_under_limit(fake_redis):
    result = await check_send_rate_limits(
        fake_redis,
        fingerprint_hash="fp1",
        link_id=1,
        per_fingerprint_limit=3,
        per_fingerprint_window=60,
        per_link_limit=100,
        per_link_window=60,
        global_limit=1000,
        global_window=60,
    )
    assert result.allowed is True


async def test_blocks_when_fingerprint_limit_exceeded(fake_redis):
    kwargs = dict(
        fingerprint_hash="fp2",
        link_id=1,
        per_fingerprint_limit=2,
        per_fingerprint_window=60,
        per_link_limit=100,
        per_link_window=60,
        global_limit=1000,
        global_window=60,
    )
    assert (await check_send_rate_limits(fake_redis, **kwargs)).allowed is True
    assert (await check_send_rate_limits(fake_redis, **kwargs)).allowed is True
    third = await check_send_rate_limits(fake_redis, **kwargs)
    assert third.allowed is False
    assert third.scope == "fingerprint"


async def test_different_fingerprints_have_independent_limits(fake_redis):
    kwargs = dict(
        link_id=1,
        per_fingerprint_limit=1,
        per_fingerprint_window=60,
        per_link_limit=100,
        per_link_window=60,
        global_limit=1000,
        global_window=60,
    )
    assert (await check_send_rate_limits(fake_redis, fingerprint_hash="a", **kwargs)).allowed is True
    assert (await check_send_rate_limits(fake_redis, fingerprint_hash="b", **kwargs)).allowed is True


async def test_per_link_limit_trips_across_fingerprints(fake_redis):
    kwargs = dict(
        link_id=42,
        per_fingerprint_limit=100,
        per_fingerprint_window=60,
        per_link_limit=1,
        per_link_window=60,
        global_limit=1000,
        global_window=60,
    )
    assert (await check_send_rate_limits(fake_redis, fingerprint_hash="a", **kwargs)).allowed is True
    second = await check_send_rate_limits(fake_redis, fingerprint_hash="b", **kwargs)
    assert second.allowed is False
    assert second.scope == "link"
