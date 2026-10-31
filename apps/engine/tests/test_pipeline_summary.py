from datetime import UTC, datetime

from engine.pipeline.summary import Report, render

RUN = {
    "id": 5,
    "trigger": "schedule",
    "status": "ok",
    "changed": True,
    "started_at": datetime(2026, 11, 5, 6, 15, tzinfo=UTC),
    "finished_at": datetime(2026, 11, 5, 6, 17, tzinfo=UTC),
    "ingest_run_id": 9,
    "model_run_ids": [40, 41],
    "simulation_run_id": 8,
    "error": None,
    "summary": {
        "decision": "ingest inserted 0 / updated 1 matches",
        "timings_s": {"ingest": 14.1, "predict": 20.3, "simulate": 30.2},
        "changes": {"newly_finished": ["Arsenal v Bayern 2-1 (LEAGUE_PHASE MD4)"],
                    "kickoff_changed": ["Inter v Ajax: a -> b"], "new_fixtures": []},
    },
}  # fmt: skip


def test_full_report():
    report = Report(
        run=RUN,
        season="2026-27",
        primary_model="elo",
        next_matchday="LEAGUE_PHASE matchday 5",
        next_predictions=[
            {"kickoff_utc": datetime(2026, 11, 24, 17, 45, tzinfo=UTC), "home": "Inter",
             "away": "Ajax", "p_home": 0.6, "p_draw": 0.25, "p_away": 0.15},
        ],
        simulation_run_id=8,
        simulation_as_of="2026-11-04",
        simulation_top=[
            {"team": "Arsenal", "expected_points": 17.25, "p_top8": 0.8, "p_playoff": 0.2,
             "p_r16": 0.9, "p_qf": 0.6, "p_sf": 0.4, "p_final": 0.25, "p_win": 0.15},
        ],
        scoreboard=[
            {"model": "elo", "n": 18, "log_loss": 0.95, "rps": 0.2, "brier": 0.55,
             "accuracy": 0.5, "uniform_log_loss": 1.0986, "uniform_rps": 0.23,
             "uniform_brier": 0.6667, "uniform_accuracy": 0.44},
        ],
    )  # fmt: skip
    md = render(report)
    assert md.startswith("## Matchday pipeline run 5: `ok`")
    assert "| changed | yes |" in md
    assert "| model runs | 40, 41 |" in md
    assert "| timings (s) | ingest 14.1, predict 20.3, simulate 30.2 |" in md
    assert "### Matches newly finished (1)\n\n- Arsenal v Bayern 2-1 (LEAGUE_PHASE MD4)" in md
    assert "<summary>kickoff changed (1)</summary>" in md
    assert "new fixtures" not in md
    assert "### Next matchday: LEAGUE_PHASE matchday 5" in md
    assert "| 2026-11-24 17:45Z | Inter | Ajax | 60.0% | 25.0% | 15.0% |" in md
    assert "| 1 | Arsenal | 17.2 | 80.0% | 20.0% | 90.0% | 60.0% | 40.0% | 25.0% | 15.0% |" in md
    assert "| elo | 18 | 0.9500 | 0.2000 | 0.5500 | 0.5000 | 1.0986 |" in md


def test_failed_run_with_empty_sections():
    run = RUN | {
        "status": "failed",
        "changed": None,
        "model_run_ids": None,
        "simulation_run_id": None,
        "error": "RuntimeError('boom')",
        "summary": {"step": "predict", "changes": {}},
    }
    md = render(Report(run=run, season="2026-27"))
    assert "`failed`" in md and "**Failed in `predict`:**" in md and "RuntimeError('boom')" in md
    assert "| changed | - |" in md and "| model runs | - |" in md
    assert "### Matches newly finished (0)\n\nNone." in md
    assert "No upcoming match has an official primary-model prediction." in md
    assert "No simulation run yet." in md
    assert "### Scoreboard 2026-27" in md and "No finished match this season" in md
