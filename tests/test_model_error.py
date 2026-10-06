from datalens.ai.base import is_model_error


def test_old_cli_rejecting_a_model_counts_as_a_model_error():
    msg = "API Error: 400 Claude Code 2.1.220 does not support this model; version 2.1.280 or newer is required."
    assert is_model_error(msg)
    assert not is_model_error("network timeout")


def test_ai_json_with_raw_newline_in_a_string_still_parses():
    from datalens.ai.response import extract_json_from_text

    text = '```json\n{"data_story": "line one\nline two", "n": 1}\n```'
    assert extract_json_from_text(text) == {"data_story": "line one\nline two", "n": 1}
