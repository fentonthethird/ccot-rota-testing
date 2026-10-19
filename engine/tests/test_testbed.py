"""The test site's setup and reset never touch anything but the test data folder."""
import datetime as dt
from pathlib import Path

import pytest

from ccot import allocate, codec, importer, testbed
from ccot import windows as W
from ccot.store import Store
from conftest import REAL_WORKBOOK

pytestmark = pytest.mark.skipif(not REAL_WORKBOOK.exists(), reason="real workbook not present")


def run(tmp_path, monkeypatch, *args):
    monkeypatch.setenv("CCOT_DATA", str(tmp_path / "data"))
    monkeypatch.setattr(testbed, "PAYLOADS", [tmp_path / "payload.enc", tmp_path / "view.enc"])
    testbed.main(list(args))
    return Store(tmp_path / "data")


def submit(st, wid, ini):
    w = st.window(wid)
    days = [1] * W.length(w)
    importer.import_text(st, wid, codec.encode(ini, dt.date.fromisoformat(w["start"]), days, token=w["tokens"][ini]))


def test_setup_reset_and_new_round(tmp_path, monkeypatch, capsys):
    st = run(tmp_path, monkeypatch, "setup", "--workbook", str(REAL_WORKBOOK))
    state = st.load("testbed.json")
    wid = state["window"]
    assert wid == "2026-27-TRIAL-1" and st.settings()["site_url"].endswith("/ccot-rota-testing/")
    links = next(st.root.glob("LINKS - *.txt")).read_text()
    assert "fentonthethird.github.io/ccot-rota-testing/?c=AWB" in links
    tokens = st.window(wid)["tokens"]
    shifts_before = len(st.year("2026-27")["shifts"])

    submit(st, wid, "AWB")
    allocate.run(st, wid, time_limit=20)
    allocate.accept(st, wid)
    assert len(st.year("2026-27")["shifts"]) > shifts_before

    st = run(tmp_path, monkeypatch, "reset")
    w = st.window(wid)
    assert w["tokens"] == tokens and not w["submissions"] and not w["draft"] and w["status"] == "open"
    assert len(st.year("2026-27")["shifts"]) == shifts_before
    submit(st, wid, "AWB")  # links from setup still work after a reset

    st = run(tmp_path, monkeypatch, "new-round")
    state = st.load("testbed.json")
    assert state["window"] == "2026-27-TRIAL-2" and state["round"] == 2
    assert st.window_ids() == ["2026-27-TRIAL-2"]
    assert not st.window("2026-27-TRIAL-2")["submissions"]
    assert "TRIAL-2" in next(st.root.glob("LINKS - *.txt")).read_text()


def test_setup_refuses_to_overwrite_without_force(tmp_path, monkeypatch):
    run(tmp_path, monkeypatch, "setup", "--workbook", str(REAL_WORKBOOK))
    with pytest.raises(SystemExit):
        run(tmp_path, monkeypatch, "setup", "--workbook", str(REAL_WORKBOOK))


def test_refuses_the_live_folder(monkeypatch):
    monkeypatch.setenv("CCOT_DATA", str(Path.home() / "Documents" / "Claude" / "CCOT Rota App" / "CCOT Rota Data"))
    with pytest.raises(SystemExit, match="LIVE"):
        testbed.main(["status"])
