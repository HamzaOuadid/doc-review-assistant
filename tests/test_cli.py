"""Smoke tests for the Typer CLI."""
from typer.testing import CliRunner

from doc_review.cli import app

runner = CliRunner()


def test_extract_command_runs_on_a_real_corpus_document():
    result = runner.invoke(app, ["extract", "cadrenal_msa"])
    assert result.exit_code == 0
    assert "governing_law" in result.stdout


def test_extract_command_rejects_unknown_document():
    result = runner.invoke(app, ["extract", "not-a-real-doc"])
    assert result.exit_code != 0


def test_demo_command_runs_end_to_end():
    result = runner.invoke(app, ["demo"])
    assert result.exit_code == 0
    assert "UNCERTAIN" in result.stdout
    assert "INCLUDE" in result.stdout
    assert "Totals across" in result.stdout


def test_evaluate_command_prints_confidently_wrong_rates():
    result = runner.invoke(app, ["evaluate"])
    assert result.exit_code == 0
    assert "Confidently-wrong rate" in result.stdout
    assert "forced-binary" in result.stdout


def test_evaluate_command_json_output_is_parseable():
    import json

    result = runner.invoke(app, ["evaluate", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert "three_state" in payload
