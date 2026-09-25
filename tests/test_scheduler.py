"""Agendador da atualização automática (scripts/scheduler.py)."""

import importlib.util
from datetime import datetime
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "scheduler", Path(__file__).resolve().parents[1] / "scripts" / "scheduler.py"
)
scheduler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scheduler)

BRT = scheduler.BRASILIA


def test_next_run_is_today_before_the_hour():
    now = datetime(2026, 9, 25, 5, 59, tzinfo=BRT)
    assert scheduler.next_run(now) == datetime(2026, 9, 25, scheduler.UPDATE_HOUR, tzinfo=BRT)


@pytest.mark.parametrize("hour,minute", [(6, 0), (6, 1), (23, 59)])
def test_next_run_is_tomorrow_at_or_after_the_hour(hour, minute):
    now = datetime(2026, 9, 25, hour, minute, tzinfo=BRT)
    assert scheduler.next_run(now) == datetime(2026, 9, 26, scheduler.UPDATE_HOUR, tzinfo=BRT)


def test_daily_run_is_weather_only_and_skips_validation(monkeypatch):
    calls = []
    monkeypatch.setattr(scheduler.subprocess, "call", lambda args: calls.append(args) or 0)
    scheduler.run(full=False)
    assert calls == [scheduler.PIPELINE + ["--only", "weather", "--skip-validation"]]


def test_full_run_uses_every_source_with_validation(monkeypatch):
    calls = []
    monkeypatch.setattr(scheduler.subprocess, "call", lambda args: calls.append(args) or 0)
    scheduler.run(full=True)
    assert calls == [scheduler.PIPELINE]


def test_failure_is_logged_not_raised(monkeypatch, capsys):
    monkeypatch.setattr(scheduler.subprocess, "call", lambda args: 1)
    scheduler.run(full=True)
    assert "FALHOU" in capsys.readouterr().out
