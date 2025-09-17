from datetime import datetime, timedelta, time

from amp_autoshutdown.config import Config
from amp_autoshutdown.monitor import Monitor, ShutdownDecider


def make_config(**overrides):
    cfg = Config()
    for key, value in overrides.items():
        setattr(cfg, key, value)
    return cfg


def test_shutdown_decider_triggers_after_idle():
    cfg = make_config(idle_delay_minutes=1, global_player_threshold=0)
    decider = ShutdownDecider(cfg)
    decider.state.last_activity = datetime.utcnow() - timedelta(minutes=2)
    assert decider.register_observation({"instance": 0}) is True
    # second call remains False because shutdown already flagged
    assert decider.register_observation({"instance": 0}) is False


def test_shutdown_decider_resets_on_activity():
    cfg = make_config(idle_delay_minutes=5, global_player_threshold=0)
    decider = ShutdownDecider(cfg)
    decider.state.last_activity = datetime.utcnow() - timedelta(minutes=4)
    assert decider.register_observation({"instance": 1}) is False
    decider.state.last_activity = datetime.utcnow() - timedelta(minutes=6)
    assert decider.register_observation({"instance": 0}) is True


def test_time_window_wraparound():
    assert Monitor._time_in_window(time(23, 0), "22:00", "02:00") is True
    assert Monitor._time_in_window(time(3, 0), "22:00", "02:00") is True
    assert Monitor._time_in_window(time(15, 0), "22:00", "02:00") is False
