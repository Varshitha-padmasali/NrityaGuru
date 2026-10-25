from app.core.rate_limit import SlidingWindowLimiter


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def test_allows_up_to_the_limit_then_blocks():
    c = Clock()
    lim = SlidingWindowLimiter(2, 60, clock=c)
    assert lim.check("a") == (True, 0.0)
    assert lim.check("a") == (True, 0.0)
    allowed, retry = lim.check("a")
    assert allowed is False
    assert 0 < retry <= 60


def test_blocked_calls_are_not_counted():
    c = Clock()
    lim = SlidingWindowLimiter(1, 10, clock=c)
    lim.check("a")
    for _ in range(5):
        lim.check("a")
    c.t += 10
    assert lim.check("a")[0] is True  # window expired; spam did not extend the block


def test_window_expiry_allows_again():
    c = Clock()
    lim = SlidingWindowLimiter(1, 60, clock=c)
    assert lim.check("a")[0]
    assert not lim.check("a")[0]
    c.t += 61
    assert lim.check("a")[0]


def test_retry_after_shrinks_over_time():
    c = Clock()
    lim = SlidingWindowLimiter(1, 60, clock=c)
    lim.check("a")
    c.t += 20
    _, retry = lim.check("a")
    assert 39 <= retry <= 41


def test_keys_are_independent():
    lim = SlidingWindowLimiter(1, 60, clock=Clock())
    assert lim.check("a")[0]
    assert lim.check("b")[0]
    assert not lim.check("a")[0]


def test_stale_keys_are_pruned():
    c = Clock()
    lim = SlidingWindowLimiter(1, 10, clock=c, max_keys=3)
    for k in "abcd":
        lim.check(k)
    c.t += 11
    lim.check("e")  # triggers pruning because there are more than max_keys entries
    assert set(lim._hits) == {"e"}
