from interdomain.streaming.kafka import resolve_start_offset


def test_resumes_at_stored_offset_when_kafka_still_has_it():
    assert resolve_start_offset(stored=500, low=100, high=900) == (500, None)


def test_caught_up_consumer_resumes_at_high_watermark():
    assert resolve_start_offset(stored=900, low=100, high=900) == (900, None)


def test_expired_messages_jump_to_oldest_and_report_the_gap():
    offset, warning = resolve_start_offset(stored=50, low=100, high=900)

    assert offset == 100
    assert "50 messages expired" in warning


def test_offset_past_newest_means_topic_was_recreated():
    offset, warning = resolve_start_offset(stored=5_000, low=0, high=40)

    assert offset == 0
    assert "recreated" in warning
