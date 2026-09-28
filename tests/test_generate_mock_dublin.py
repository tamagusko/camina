from scripts.generate_mock_dublin import CLASSES, STREETS, generate


def test_direction_counts_are_optional_and_sum_to_class_count() -> None:
    data = generate()
    readings = data["sensor_readings"]
    sensor_ids = {reading["sensor_id"] for reading in readings}
    directional_sensor_ids = {
        reading["sensor_id"] for reading in readings if "direction_ab_count" in reading
    }

    assert len(directional_sensor_ids) > len(STREETS) / 2
    assert directional_sensor_ids < sensor_ids

    for reading in readings:
        has_ab = "direction_ab_count" in reading
        has_ba = "direction_ba_count" in reading
        assert has_ab == has_ba
        if has_ab:
            assert reading["direction_ab_count"] + reading["direction_ba_count"] == reading["count"]
            assert reading["class_name"] in CLASSES


def test_speed_histograms_hold_every_timed_road_user_in_the_edge_bins() -> None:
    from camina.core.counter import SPEED_BIN_EDGES, SPEED_BINS
    from scripts import generate_mock_dublin

    assert generate_mock_dublin.SPEED_BIN_EDGES == SPEED_BIN_EDGES
    readings = generate()["sensor_readings"]
    with_hist = [r for r in readings if "speed_hist_kmh" in r]
    assert with_hist
    for reading in with_hist:
        assert reading["count"] >= 5
        assert len(reading["speed_hist_kmh"]) == SPEED_BINS
        assert sum(reading["speed_hist_kmh"]) == reading["count"]


def test_mock_speeds_are_plausible_per_class() -> None:
    # Window means, km/h: walking stays at walking pace, cars at urban speeds.
    readings = generate()["sensor_readings"]
    bounds = {"person": (3.5, 6.5), "e-scooter": (12, 21), "car": (25, 40), "bus": (17, 30)}
    for reading in readings:
        low_high = bounds.get(reading["class_name"])
        if low_high and reading["count"] >= 20:
            assert low_high[0] <= reading["avg_speed_kmh"] <= low_high[1], reading
