from interdomain.processing.anomalies import is_withdrawal_spike, withdrawal_ratio


def test_withdrawal_ratio():
    assert withdrawal_ratio(["announcement", "withdrawal", "withdrawal", "announcement"]) == 0.5


def test_detects_withdrawal_spike():
    events = ["withdrawal"] * 9 + ["announcement"] * 11
    assert is_withdrawal_spike(events, threshold=0.40, minimum_events=20)
