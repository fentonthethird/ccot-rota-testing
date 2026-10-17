"""Setup and reset for the TEST site. Only ever touches the test data folder and this repository.

  ./testbed setup     seed the test data from the workbook, create the trial window, write the links
  ./testbed reset     put the test data back to how it was after setup; links keep working
  ./testbed new-round like reset, but with fresh links so testers' phones start blank too
  ./testbed status    what state the test is in
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import subprocess
import sys
from pathlib import Path

from . import calendar as cal
from . import windows as W
from . import xlsx_import
from .store import Store

REPO = Path(__file__).resolve().parents[2]
PAYLOAD = REPO / "docs" / "rota" / "payload.enc"
SITE = "https://fentonthethird.github.io/ccot-rota-testing/"
DEFAULT_WORKBOOK = Path.home() / "Library/Mobile Documents/com~apple~CloudDocs/Downloads/Outreach Cons Rota v2.xlsx"
BASELINE = ".baseline"
STATE = "testbed.json"
KEEP = ("settings.json", "roster.json", "history.json", "years", "windows")


def _guard(st: Store) -> None:
    if st.root.resolve() == (Path.home() / "Documents" / "CCOT Rota Data").resolve():
        sys.exit("refusing: %s is the LIVE data folder" % st.root)


def _state(st: Store) -> dict:
    return st.load(STATE, {})


def _snapshot(st: Store) -> None:
    base = st.path(BASELINE)
    if base.exists():
        shutil.rmtree(base)
    base.mkdir()
    for name in KEEP:
        src = st.path(name)
        if src.is_dir():
            shutil.copytree(src, base / name, ignore=shutil.ignore_patterns("*.heatmap.html"))
        elif src.exists():
            shutil.copy2(src, base / name)


def _restore(st: Store) -> None:
    base = st.path(BASELINE)
    if not base.exists():
        sys.exit("no baseline saved; run `./testbed setup` first")
    for name in KEEP:
        dst = st.path(name)
        if dst.is_dir():
            shutil.rmtree(dst)
        elif dst.exists():
            dst.unlink()
        src = base / name
        if src.is_dir():
            shutil.copytree(src, dst)
        elif src.exists():
            shutil.copy2(src, dst)
    exports = st.path("exports")
    if exports.exists():
        shutil.rmtree(exports)


def _links_file(st: Store, wid: str) -> Path:
    out = st.path("LINKS - %s.txt" % wid)
    rows = W.links(st, wid)
    lines = ["CCOT rota TEST links for window %s" % wid, "Send each person their own link. Codes only validate against the link they were made from.", ""]
    for r in rows:
        lines += ["%s (%s)" % (r["name"], r["initials"]), r["url"], ""]
    for old in st.root.glob("LINKS - *.txt"):
        old.unlink()
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def _unpublish(push: bool) -> None:
    if not PAYLOAD.exists():
        print("test dashboard: nothing published")
        return
    tracked = subprocess.run(["git", "-C", str(REPO), "ls-files", "--error-unmatch", str(PAYLOAD)], capture_output=True).returncode == 0
    if not tracked:
        PAYLOAD.unlink()
        print("test dashboard: removed unpublished local payload")
        return
    subprocess.run(["git", "-C", str(REPO), "rm", "-q", str(PAYLOAD)], check=True)
    subprocess.run(["git", "-C", str(REPO), "-c", "commit.gpgsign=false", "commit", "-q", "-m", "Reset test dashboard"], check=True)
    if not push:
        print("test dashboard: removal committed; run `git push` to take it off the site")
        return
    r = subprocess.run(["git", "-C", str(REPO), "push", "-q"], env={**__import__("os").environ, "GIT_TERMINAL_PROMPT": "0"}, capture_output=True, text=True)
    if r.returncode == 0:
        print("test dashboard: taken down (pushed)")
    else:
        print("test dashboard: removal committed but the push failed; run `git push` yourself\n  " + (r.stderr.strip().splitlines() or [""])[-1])


def cmd_setup(a, st: Store) -> None:
    _guard(st)
    if st.exists() and not a.force:
        sys.exit("test data already exists at %s. Use `./testbed reset`, or `./testbed setup --force` to rebuild it from scratch." % st.root)
    if st.root.exists():
        shutil.rmtree(st.root)
    st.init()
    wb = Path(a.workbook).expanduser()
    if a.empty:
        print("starting with an empty year (no shifts imported)")
        rep = xlsx_import.import_workbook(st, str(wb), a.year)
        y = st.year(a.year)
        y["shifts"], y["unfilled"], y["notes"], y["log"] = {}, [], {}, []
        st.save_year(y)
    else:
        rep = xlsx_import.import_workbook(st, str(wb), a.year)
        print("imported %d consultants and %d existing shifts from the workbook" % (rep["consultants"], rep["shifts"]))
    s = st.settings()
    s["site_url"] = SITE
    st.save_settings(s)
    if a.deadline is None:
        a.deadline = dt.date.today() + dt.timedelta(days=14)
    wid = "%s-TRIAL-1" % a.year
    W.create(st, wid, a.start, a.end, a.deadline)
    st.save(STATE, {"window": wid, "round": 1, "year": a.year, "start": a.start.isoformat(), "end": a.end.isoformat(),
                    "deadline": a.deadline.isoformat() if a.deadline else None, "created": dt.datetime.now().isoformat(timespec="seconds")})
    _snapshot(st)
    out = _links_file(st, wid)
    print("trial window %s: %s to %s, deadline %s" % (wid, a.start, a.end, a.deadline or "none"))
    print("links written to: %s" % out)
    print("baseline saved; `./testbed reset` returns to exactly this point")


def cmd_reset(a, st: Store) -> None:
    _guard(st)
    state = _state(st)
    _restore(st)
    print("test data restored to the baseline (submissions, drafts, allocations, swaps and overrides cleared)")
    print("links still work: %s" % _links_file(st, state["window"]))
    if not a.keep_site:
        _unpublish(push=not a.no_push)
    print("testers' marks are saved on their own phones; they can tap 'All unavailable' to clear, or use `./testbed new-round` for blank links")


def cmd_new_round(a, st: Store) -> None:
    _guard(st)
    state = _state(st)
    _restore(st)
    n = int(state.get("round", 1)) + 1
    old = state["window"]
    for p in st.path("windows").glob("*.json"):
        p.unlink()
    wid = "%s-TRIAL-%d" % (state["year"], n)
    deadline = a.deadline or (dt.date.fromisoformat(state["deadline"]) if state.get("deadline") else None)
    W.create(st, wid, dt.date.fromisoformat(state["start"]), dt.date.fromisoformat(state["end"]), deadline)
    state.update({"window": wid, "round": n, "deadline": deadline.isoformat() if deadline else None})
    st.save(STATE, state)
    _snapshot(st)
    if not a.keep_site:
        _unpublish(push=not a.no_push)
    print("round %d: window %s replaces %s. Old links no longer validate; phones start blank." % (n, wid, old))
    print("new links written to: %s" % _links_file(st, wid))


def cmd_status(a, st: Store) -> None:
    _guard(st)
    if not st.exists():
        print("not set up; run `./testbed setup`")
        return
    state = _state(st)
    w = st.window(state["window"])
    print("test data: %s" % st.root)
    print("round %s, window %s (%s to %s), deadline %s, status %s" % (state.get("round"), w["id"], w["start"], w["end"], w.get("deadline") or "none", w.get("status")))
    print("codes received: %d (%s)" % (len(w.get("submissions") or {}), ", ".join(sorted(w.get("submissions") or {})) or "none"))
    print("draft: %s" % ("yes" if w.get("draft") else "no"))
    print("dashboard published: %s" % ("yes" if PAYLOAD.exists() else "no"))
    print("links: %s" % next(iter(sorted(st.root.glob("LINKS - *.txt"))), "missing"))


def _date(s: str) -> dt.date:
    return dt.date.fromisoformat(s)


def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="testbed", description="Set up and reset the CCOT rota TEST site.")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("setup", help="seed the test data and create the trial window")
    s.add_argument("--workbook", default=str(DEFAULT_WORKBOOK))
    s.add_argument("--year", default="2026-27")
    s.add_argument("--start", type=_date, default=dt.date(2027, 1, 1))
    s.add_argument("--end", type=_date, default=dt.date(2027, 3, 31))
    s.add_argument("--deadline", type=_date, default=None)
    s.add_argument("--empty", action="store_true", help="start the year with no shifts instead of importing them")
    s.add_argument("--force", action="store_true", help="wipe and rebuild the test data")
    s.set_defaults(fn=cmd_setup)
    s = sub.add_parser("reset", help="back to the baseline; links keep working")
    s.add_argument("--keep-site", action="store_true", help="leave the published test dashboard up")
    s.add_argument("--no-push", action="store_true", help="commit the dashboard removal but do not push")
    s.set_defaults(fn=cmd_reset)
    s = sub.add_parser("new-round", help="back to the baseline with fresh links")
    s.add_argument("--deadline", type=_date, default=None)
    s.add_argument("--keep-site", action="store_true")
    s.add_argument("--no-push", action="store_true")
    s.set_defaults(fn=cmd_new_round)
    s = sub.add_parser("status", help="show the state of the test")
    s.set_defaults(fn=cmd_status)
    a = p.parse_args(argv)
    st = Store()
    a.fn(a, st)


if __name__ == "__main__":
    main()
