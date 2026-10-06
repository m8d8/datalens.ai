import openpyxl

from datalens import analyze
from datalens.config import Config
from datalens.profiling.naming import is_placeholder_name


def _fields(result, obj=None):
    o = result.schema_json["objects"][0] if obj is None else next(x for x in result.schema_json["objects"] if x["object"] == obj)
    return {f["path"] for f in o["fields"]}


def _run(path, **kw):
    return analyze({"source": "file", "path": str(path)}, Config(sample_size=0, **kw))


def test_placeholder_names():
    for n in ("", None, "  ", "col_6", "Column1", "column 12", "Unnamed: 3", "Field2"):
        assert is_placeholder_name(n)
    for n in ("Channel Name", "column_name", "Availability", "Total Column"):
        assert not is_placeholder_name(n)


def test_csv_drops_empty_placeholder_columns_only(tmp_path):
    p = tmp_path / "d.csv"
    p.write_text("name,Unnamed: 1,Column2,notes,empty_named,\nann,,,x,,\nbob, ,,y,,\n")
    f = _fields(_run(p))
    # Column2 / Unnamed: 1 stand out from the real names and are empty; the blank header too.
    # Named columns stay even if empty.
    assert f == {"name", "notes", "empty_named"}


def test_generic_header_convention_keeps_empty_columns(tmp_path):
    p = tmp_path / "d.csv"
    p.write_text("Column1,Column2,Column3\na,,c\nb,,d\n")
    assert _fields(_run(p)) == {"Column1", "Column2", "Column3"}


def test_placeholder_column_with_data_is_kept(tmp_path):
    p = tmp_path / "d.csv"
    p.write_text("name,Column1\nann,\nbob,hello\n")
    assert _fields(_run(p)) == {"name", "Column1"}


def test_excel_blank_and_generated_headers(tmp_path):
    p = tmp_path / "d.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["Channel", None, "Column1", "Genre", None])
    ws.append(["CNN", None, None, "News", "extra"])
    ws.append(["NBC", None, None, None, "more"])
    wb.save(p)
    f = _fields(_run(p), "Sheet1")
    # Blank header col_2 and generated Column1 are empty and out of line: dropped.
    # The blank header col_5 holds data, so it stays.
    assert f == {"Channel", "Genre", "col_5"}


def test_excel_generic_convention_keeps_empty_column(tmp_path):
    p = tmp_path / "g.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "S"
    ws.append(["Column1", "Column2", "Column3"])
    ws.append(["a", None, "c"])
    ws.append(["b", None, "d"])
    wb.save(p)
    assert _fields(_run(p), "S") == {"Column1", "Column2", "Column3"}
