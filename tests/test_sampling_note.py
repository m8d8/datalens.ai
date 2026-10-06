from datalens import cli


def _out(capsys, schema, n):
    with cli.console.capture() as cap:
        cli._print_sampling_note(schema, n)
    return " ".join(cap.get().split())


def test_note_when_sampled(capsys):
    out = _out(capsys, {"objects": [{"object": "big", "sampled": 1000, "total_rows": 5000}]}, 1000)
    assert "sample" in out and "big" in out and "5,000" in out and "--full-scan" in out


def test_note_when_cap_hit_and_total_unknown(capsys):
    out = _out(capsys, {"objects": [{"object": "db", "sampled": 1000}]}, 1000)
    assert "more than that" in out


def test_no_note_for_small_or_full_scans(capsys):
    assert _out(capsys, {"objects": [{"object": "s", "sampled": 50, "total_rows": 50}]}, 1000) == ""
    assert _out(capsys, {"objects": [{"object": "b", "sampled": 9, "total_rows": 9}]}, 0) == ""
