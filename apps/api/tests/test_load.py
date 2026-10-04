from app.modules.queues.load import marker_for, LoadLevel

def test_marker_label_under_1000():
    assert marker_for(37, [1, 10, 37, 50]).label == "37"

def test_marker_label_over_1000():
    assert marker_for(1000, [1, 10, 1000, 2000]).label == "> 1 тыс."
