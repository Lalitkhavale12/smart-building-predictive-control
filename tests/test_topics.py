"""Topic-contract unit tests (Phase 2 plan 01, IOT-03). Brokerless, stdlib only."""

import pytest

from sim import config as cfg
from iot import topics


def test_telemetry_command_status_for_sample_room():
    assert topics.telemetry_topic("classroom_A") == "building/classroom_A/telemetry"
    assert topics.command_topic("classroom_A", "hvac") == "building/classroom_A/command/hvac"
    assert topics.command_topic("classroom_A", "light") == "building/classroom_A/command/light"
    assert topics.status_topic("classroom_A") == "building/classroom_A/status"
    assert topics.command_filter("classroom_A") == "building/classroom_A/command/#"


def test_command_topic_rejects_bad_device():
    with pytest.raises(AssertionError):
        topics.command_topic("classroom_A", "fan")


def test_every_config_room_produces_slash_free_topics():
    assert len(cfg.ROOMS) == 4
    for room in cfg.ROOMS:
        assert "/" not in room, f"room name {room!r} would break topic levels"
        for topic in (
            topics.telemetry_topic(room),
            topics.command_topic(room, "hvac"),
            topics.command_topic(room, "light"),
            topics.status_topic(room),
        ):
            assert topic.startswith(f"building/{room}/")
            assert "//" not in topic


def test_value_sets_mirror_sim_config():
    assert topics.VALID_HVAC == frozenset(cfg.Q_HVAC)
    assert tuple(topics.VALID_LIGHT) == (0, 1)


def test_bridge_wildcards():
    assert topics.WILDCARD_TELEMETRY == "building/+/telemetry"
    assert topics.WILDCARD_STATUS == "building/+/status"
