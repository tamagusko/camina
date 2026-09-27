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
