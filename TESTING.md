# CCOT rota TEST site

A separate copy of the CCOT rota for trialling before launch. It has its own website, its own data
folder and its own links. Nothing here touches the live rota.

| | Test | Live |
|---|---|---|
| Website | https://fentonthethird.github.io/ccot-rota-testing/ | https://fentonthethird.github.io/ccot-rota/ |
| Project folder | `~/Documents/Claude/ccot-rota-testing` | `~/Documents/Claude/CCOT Rota App/ccot-rota` |
| Data folder | `~/Documents/Claude/CCOT Rota Testing Data` | `~/Documents/Claude/CCOT Rota App/CCOT Rota Data` |
| Colour | plum, marked "TEST" | NHS blue |

The test app keeps its own saved marks and offline copy on each phone, so a tester can use both
sites without one affecting the other.

## Running a trial

```bash
cd ~/Documents/Claude/ccot-rota-testing
open "$HOME/Documents/Claude/CCOT Rota Testing Data"   # the LINKS file is in here; send each tester their own link
./ccot status 2026-27-TRIAL-1                    # who has sent a code
./ccot import 2026-27-TRIAL-1                    # paste codes or whole messages, then Ctrl-D
./ccot heatmap 2026-27-TRIAL-1 --html            # offers per date
./ccot allocate 2026-27-TRIAL-1                  # see how their choices map to the rota
./ccot accept 2026-27-TRIAL-1                    # write it into the test year
./ccot publish && git add docs && git commit -m "Publish test rota" && git push   # test dashboard
```

`./testbed status` shows the window name if it has moved on to a later round.

## Two dashboards

| | Address | Shows | Publish with |
|---|---|---|---|
| Full | `.../ccot-rota-testing/rota/` | rota with job plan and locum colouring, job plans, locum counts, Summary and WLI money, changes | `./ccot publish` |
| Rota only | `.../ccot-rota-testing/rota-view/` | rota by month (names only), highlight a name, job plan shifts done against quota | `./ccot publish --view rota` |

Each has its own passphrase and its own encrypted file. The rota-only file is built separately and
does not contain any money, locum counts, shift types, notes or change log, so its passphrase
cannot reveal them. Publish both after each change:

```bash
./ccot publish && ./ccot publish --view rota && git add docs && git commit -m "Publish test rota" && git push
```

Anyone with the rota-only view can still count a person's days on the calendar, so total shifts
per person are visible by counting; which of them were paid as locum is not.

Testers who are not consultants can be added to the test roster, then given a link:

```bash
./ccot roster add ABC "Alex Example" --weekday 5 --weekend 1
./ccot links 2026-27-TRIAL-1
```

## Resetting

```bash
./testbed reset       # back to the starting point; links already sent keep working
./testbed new-round   # back to the starting point with brand new links; testers' phones start blank
./testbed status      # where the trial is up to
./testbed setup --force   # rebuild everything from the workbook (new links)
```

`reset` clears every code received, every draft and allocation, and every swap and override, and
takes both test dashboards down. Testers' marks stay on their phones; they can tap "All unavailable"
to start again. `new-round` gives a new window name, so old links stop working and phones open
blank. Add `--keep-site` to leave the test dashboard up, or `--no-push` to commit without pushing.

`./testbed setup --empty` starts the trial year with no existing shifts instead of the workbook's.
`./testbed setup --start 2027-01-01 --end 2027-01-31` trials a shorter window.

## Moving changes to the live site

Changes made here are not copied across automatically. When something tested here should go
live, make the same change in `~/Documents/Claude/CCOT Rota App/ccot-rota`.
