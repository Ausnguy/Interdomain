from interdomain.ingestion.backoff import backoff_delay


def test_ceiling_doubles_each_attempt():
    ceilings = [backoff_delay(n, base=1.0, cap=60.0, rng=lambda: 1.0) for n in range(4)]
    assert ceilings == [1.0, 2.0, 4.0, 8.0]


def test_ceiling_is_capped():
    assert backoff_delay(20, base=1.0, cap=60.0, rng=lambda: 1.0) == 60.0


def test_jitter_scales_the_ceiling():
    assert backoff_delay(3, base=1.0, cap=60.0, rng=lambda: 0.5) == 4.0
    assert backoff_delay(3, base=1.0, cap=60.0, rng=lambda: 0.0) == 0.0


def test_negative_attempt_is_treated_as_first():
    assert backoff_delay(-5, base=1.0, cap=60.0, rng=lambda: 1.0) == 1.0
