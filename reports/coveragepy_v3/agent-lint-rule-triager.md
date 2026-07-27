# Lint-derived findings (19 tier-1 of 151 rules, ruff 0.16.0)

Target: `/home/danzin/projects/coveragepy/coverage` @ `6b3259ab`. Target tree **not modified**;
all execution done against a copy at `/tmp/covrepro`.

**Envelope is clean.** `version_matches_pin: true` (0.16.0 == pin), `rule_validation.unknown`,
`.removed` and `.preview_gated` all empty, `stderr` empty, `error` null, `findings_capped` false.
Counts below are comparable with the calibrated benchmark run (coverage.py tier-1 = 19; this run = 19,
no drift).

## Headline

The defect-grade residue of this run is **one new finding with two sites** (naive timestamps written
into machine-readable artifacts) plus **two merges** with findings the toolkit already had.
Sixteen of nineteen are dismissed. Measured tier-1 precision here is **3/19 ≈ 16%**, well under the
50-70% band — driven almost entirely by `B905` scoring **0 of 6** and the security family (`S302`,
`S307`, `S608`) scoring **0 of 3**. Both are calibration signals, recorded below.

---

## Confirmed defects

| Code | File:line | Failure scenario | Shape |
|---|---|---|---|
| DTZ005 | `coverage/jsonreport.py:83` | `meta.timestamp` is `datetime.now().isoformat()` — naive, **no UTC offset**. Two runs 60 real minutes apart on the DST fall-back day both emit `"2025-11-02T01:30:00"`, byte-identical. A dashboard sorting reports by `meta.timestamp` picks the newer report only by luck of input order. Across a multi-region CI fleet the same string denotes instants up to a day apart. | *(proposed)* `naive-datetime-in-a-persisted-artifact` |
| DTZ005 | `coverage/sqldata.py:368` | `meta.when` in the SQLite data file, `strftime("%Y-%m-%d %H:%M:%S")` — naive, no offset. Written precisely when `self._our_suffix` is set, i.e. **parallel mode**, which is the distributed-CI case where workers can sit in different zones. `coverage combine` merges those files; the `when` values are then unorderable. `doc/dbschema.rst:73` documents the column as public schema. | *(proposed)* `naive-datetime-in-a-persisted-artifact` |

**These are one finding with two sites** (briefing rule 2: systemic root over instance count). The
root is that coverage.py stamps time four different ways across its artifact writers:

| Writer | Expression | Timezone-recoverable? |
|---|---|---|
| `xmlreport.py:99` | `str(int(time.time() * 1000))` | **yes** — epoch ms, UTC by definition |
| `html.py:321` | `format_local_datetime(datetime.now())` | **yes** — `misc.py:290` does `.astimezone().strftime("... %z")` |
| `jsonreport.py:83` | `datetime.now().isoformat()` | **no** |
| `sqldata.py:368` | `datetime.now().strftime("%Y-%m-%d %H:%M:%S")` | **no** |

**The guarded twin is in this codebase, one import away.** `coverage/misc.py:288-290`:

```python
def format_local_datetime(dt: datetime.datetime) -> str:
    """Return a string with local timezone representing the date."""
    return dt.astimezone().strftime("%Y-%m-%d %H:%M %z")
```

The HTML reporter already calls it. The JSON reporter and the SQLite writer do not. This is the
project's own judgement that a timestamp needs an offset, applied to one backend out of the two that
need it — the established `one-concern-implemented-per-backend` pattern for this project
(cf. CRF-COVPY-0010, CRF-COVPY-0043).

Demonstrated on the copy, `TZ=America/New_York`, two instants 3600s apart straddling the 2025-11-02
fall-back:

```
run A (earlier, fold=0)   json meta.timestamp = '2025-11-02T01:30:00'   html = '... 01:30 -0400'
run B (LATER,   fold=1)   json meta.timestamp = '2025-11-02T01:30:00'   html = '... 01:30 -0500'
IDENTICAL STRING?  json meta.timestamp : True
IDENTICAL STRING?  sqlite meta.when    : True
IDENTICAL STRING?  html time_stamp     : False
```

**Classification: CONSIDER, not FIX.** Nothing inside coverage.py reads `meta.timestamp` or
`meta.when` back — I grepped `coverage/`, `tests/` and `doc/`; the only in-repo reader is
`tests/test_data.py:1054`, which asserts presence, not value. The blast radius is external consumers
of two documented, versioned artifacts. Suggested fix is one line each: route both through
`format_local_datetime`, or use `datetime.now(datetime.timezone.utc)`.

---

## Merged with scanner findings (2)

Reported once, at raised confidence — two tools agreeing is one finding with two witnesses.

| Code | Site | Scanner finding | Disposition |
|---|---|---|---|
| `E722` | `pth_file.py:13` | `scan_python_pitfalls` → `bare-except-swallows-control-flow` @ `pth_file.py:13` (FIX, high) | **Already catalogued as CRF-COVPY-0026** — "The .pth bare except hides a broken install, so every subprocess contributes nothing." Confirmed still present. Not re-litigated. Note the suppression comment is `# pylint: disable=bare-except`, which acknowledges the *style* and says nothing about the swallowed-install consequence — it does not discharge the finding. |
| `B019` | `collector.py:413` | `scan_python_pitfalls` → `lru-cache-on-method` @ `collector.py:414` (CONSIDER, high) | **Merged, confidence raised.** `@functools.cache` on `Collector.cached_mapped_file` keys on `self`, so every `Collector` ever constructed is retained for the process lifetime. Line 413 vs 414 is decorator-line vs `def`-line, same site. |

**Read the suppression comment, do not count it.** `B019` carries
`has_suppression_comment: true`, but the comment is `# pylint: disable=method-cache-max-size-none` —
a *different* pylint check, about `cache` versus `lru_cache(maxsize=None)`. It says nothing about the
instance-retention concern `B019` raises. The `has_suppression_comment` flag is line-level and
rule-agnostic; on this run it would have wrongly dismissed a finding the scanner independently
confirmed. **Recommend: the field remains a strong prior, but a triager must read the comment's
*subject* before dismissing on it.**

---

## Dismissed (16)

| Code | File:line | Why | Suppression comment present |
|---|---|---|---|
| B905 | `report.py:106` | **Deliberate truncation, load-bearing.** `zip(header, values)`. `tabular_report()` (`:248`) appends a trailing `nums.pc_covered` float to every row as the numeric sort key for `column_order["cover"] = -1`; it is intentionally not displayed. Verified for all four config combinations: `len(row) == len(header) + 1` always, surplus `[80.0]`. Adding `strict=True` would raise `ValueError` on **every text report**. | no |
| B905 | `report.py:176` | Same site, markdown formatter. Same appended sort key. | no |
| B905 | `report.py:117` | `zip(header, total_line)`. `header` (`:225-230`) and `total_line` (`:268-274`) are built by parallel `if self.branches` / `if self.config.show_missing` blocks — provably equal in all four combinations. `total_line` gets **no** appended sort key. | no |
| B905 | `report.py:188` | Same, markdown. Provably equal. | no |
| B905 | `html.py:385` | Pairwise-slide idiom: `zip(files_to_report[:-1], files_to_report[1:])`. Both slices are length `n-1` for every `n ≥ 0`. Truncation unreachable. | no |
| B905 | `sysmon.py:134` | `zip(names, args)` inside `panopticon`, defined under `if LOG:  # pragma: debugging` (`sysmon.py:64`), gated on `COVERAGE_SYSMON_LOG`. Names are decorator-supplied, args runtime — the one site here where lengths *could* differ, but the only consequence is an under-populated debug log line. Not a correctness path. | no |
| DTZ005 | `html.py:321` | **This is the guarded twin.** `format_local_datetime()` attaches the local zone and formats `%z`. Correct as written; ruff flags the inner `now()` without seeing the wrapper. | no |
| DTZ005 | `control.py:1413` | `coverage debug sys` output, human-read diagnostic field. Not persisted, not compared, not machine-parsed. | no |
| DTZ006 | `debug.py:235` | `fromtimestamp(s.st_mtime)` for a one-line debug summary of a file. Converting an epoch mtime to local wall time for human display is the *correct* behaviour here, not a defect. | no |
| S302 | `execfile.py:335` | `marshal.load` on a `.pyc` the user explicitly passed to `coverage run`. Executing user-nominated code is the tool's entire purpose; anyone who can supply a `.pyc` can supply a `.py`. Magic-number and flag parsing precede the load. **ACCEPTABLE / POLICY.** | no |
| S307 | `parser.py:662` | `eval(node.id)` guarded on the line above by `if node.id in ["True", "False", "None", "__debug__"]`. The argument is proven to be one of four literals. Zero attack surface. Dismiss with the author's own marker: `# pylint: disable=eval-used`. | **yes** |
| S608 | `sqldata.py:1017` | **False positive.** The interpolated `context_clause` is `" or ".join(["context REGEXP ?"] * len(contexts))` — a constant literal repeated. Only `?` placeholders enter the SQL text; the `--contexts` regexes are bound as parameters via `con.execute(..., contexts)`. Sibling at `:998` parameterises identically. | no |
| PLW0127 | `python.py:30` | `open = open  # pylint: disable=redefined-builtin`, under the author's comment *"Save the original `open` function so later mocks don't break us."* Not a self-assignment: LHS is a new module global, RHS the builtin — it captures `open` at import time so later mocking cannot break the module. Paired with `os = isolate_module(os)` two lines up, the same defence. Dismissed with the maintainer's stated reason. | **yes** |
| PLW3301 | `lcovreport.py:73` | Style only. `min(region.start, min(region.lines))`; `region.lines` is guarded non-empty by the comprehension filter. Suppressed citing pylint issue 9923. | **yes** |
| PLW3301 | `lcovreport.py:74` | Same, `max`. | **yes** |
| E722 | *(see Merged)* | — | yes |

Suppression-signal scorecard for this run: **5 of the 6** flagged lines were deliberate idioms and are
dismissed with the author's reason (consistent with the measured 6/6 on the calibrated run). The
sixth, `B019`, is the exception documented above — the comment addressed a different rule.

---

## Calibration answers

### B905 has NOT earned tier 1 — but the *shape* keeps it

This was the explicit calibration question. **6 of 6 sites here are false positives**, and the reason
is structural rather than accidental:

- 2 sites (`report.py:106`, `:176`) use `zip`'s truncation **deliberately and load-bearingly** — the
  surplus element is a sort key that must be dropped. `strict=True` would break every text report.
- 3 sites are **provably equal-length** by parallel construction or the pairwise-slide idiom.
- 1 site is debug-only log formatting.

The rule matches a *syntactic* absence (`strict=` not written) and has no access to the
discriminator. The catalogued shape `zip-truncates-on-length-mismatch` **does** carry that
discriminator in its `differential`, and correctly rejects five of these six unaided.

**Recommendation: demote `B905` from tier 1 to tier 2; keep the shape at FIX.** Precedent matters
here — B905 fired 16 times across the three benchmark corpora and produced exactly one confirmed
defect (idlelib `pyshell.py:1002`). A rule at 1/16 is a tier-2 breadth rule, not a "the program does
something the author did not intend" rule. **Do not weaken the scanner check**: the shape's one
confirmed instance is a genuine silent data-loss bug, and the scanner's gating is what makes it
findable without six FPs alongside.

The sixth site exposes a **gap in the existing shape's `differential`**, which currently excludes only
*provably equal-length* operands. `report.py:106` is provably **un**equal, by design. Amendment
proposed below.

### The security family (`S302`, `S307`, `S608`) scored 0/3

All three are trust-boundary rules whose premise is false in a code-execution/measurement tool.
`S608`'s miss is the most instructive: ruff flagged `sqldata.py:1017` but **missed four structurally
identical sites** — `:1044`, `:1083`, `:1113` and a fourth in `contexts_by_lineno`, all doing
`", ".join("?" * len(ids))` and appending an `IN (...)` clause. It flagged the one built with
`" or ".join([...])` and missed the ones built with `", ".join(...)`. A rule whose recall on its own
target pattern is 1-of-5, and whose one hit is a false positive, is matching surface syntax rather
than data flow. **Recommend: demote `S608` to tier 2** (it is already FP-taxonomy entry #46 from the
idlelib run — this is its second consecutive 0-score). `S302`/`S307` are worth keeping in tier 1 for
projects that are *not* code runners; note them as POLICY here rather than dropping the rules.

### `PLW3301` is style, and its autofix is not semantics-preserving

Nested `min`/`max` flattening has no defect semantics at all. Worse, the suggested rewrite changes
behaviour at the edge: `min(a, min(b))` with empty `b` raises `ValueError`, while the flattened
`min(a, *b)` raises `TypeError`. **Recommend: remove `PLW3301` from tier 1.** It is the clearest
style-grade leak in the current selection.

### Scanner recall

The scanner found neither the `zip` sites nor the datetime sites — expected for `zip` (its
differential correctly suppresses all six) and a genuine **recall gap for the datetime family**,
which the scanner has no check for at all. The proposed shape below closes it.

---

## Proposed new shapes (1 new, 1 amendment)

### 1. NEW — `naive-datetime-in-a-persisted-artifact`

Earned: confirmed true positive at two sites, concrete failure scenario demonstrated, guarded twin
present in the same codebase, and the class is invisible to every other agent in the toolkit.

```json
{
  "id": "naive-datetime-in-a-persisted-artifact",
  "title": "A naive `datetime.now()` written into a machine-read artifact, so the instant is unrecoverable",
  "agent": "python-pitfall-scanner",
  "severity": "FIX",
  "pattern": "`datetime.datetime.now()` / `.today()` / `.fromtimestamp(x)` called with NO `tz=` argument, whose result is then serialized into something another program reads: a JSON/XML/YAML report field, a database column, a filename, a cache key, an HTTP header, a log line that gets parsed. The naive value carries local wall-clock digits and drops the offset, so the emitted string is a many-to-one function of the instant. Two runs an hour apart across a DST fall-back produce byte-identical output; two runs on machines in different zones produce strings that cannot be ordered. `datetime.now()` is the common case; `fromtimestamp()` is the sharper one, because it takes an unambiguous epoch value and actively discards the offset.",
  "guarded_twin": "`datetime.datetime.now(datetime.timezone.utc)`, or `.astimezone()` followed by a format string containing `%z`/`isoformat()`. The twin is usually already in the project, serving a different output backend -- coverage.py's `misc.py:288-290` `format_local_datetime()` does `dt.astimezone().strftime('%Y-%m-%d %H:%M %z')` and its HTML reporter uses it, while the JSON reporter and the SQLite writer next door do not. Look for a helper with `local`, `utc`, `iso` or `stamp` in the name before concluding the project has no opinion.",
  "hunt": "Enumerate every naive `now()`/`today()`/`fromtimestamp()` in the project, then classify each by WHERE THE VALUE GOES, not by the call site. Follow the assignment: into a `dict` that is `json.dump`ed, into an `INSERT`/`executemany` parameter, into a template global, into a filename, into a `setAttribute`. Those are the findings. A value that is only `print`ed, logged for a human, or shown in a `--debug` dump is not. Then compare the project's artifact writers against each other -- when N backends each stamp time and they do not agree on the format, the minority that omits the offset is the bug and the majority is the fix.",
  "expected": "a timestamp written for another program to read denotes exactly one instant, and two timestamps from the same emitter can be ordered.",
  "caught_as": "SILENT -- always. The string looks perfectly well-formed; it is simply ambiguous. Failures surface as an out-of-order report history, a cache that misses or wrongly hits for one hour a year, a 'latest run' that is not the latest, or a diff between two artifacts that disagree about when the same run happened. Nothing raises, and it is untestable without pinning `TZ` and `fold`.",
  "confirmed_examples": [
    "coverage.py coverage/jsonreport.py:83 -- `meta.timestamp` = `datetime.now().isoformat()`; two runs 3600s apart across the 2025-11-02 US fall-back both emit '2025-11-02T01:30:00'. Verified on a copy with TZ=America/New_York.",
    "coverage.py coverage/sqldata.py:368 -- `meta.when` in the SQLite data file, written only in parallel mode (`self._our_suffix`), i.e. exactly the distributed-CI case where workers may differ in zone. Documented public schema at doc/dbschema.rst:73."
  ],
  "validation": "confirmed",
  "references": [
    "ruff DTZ005 / DTZ006 (flake8-datetimez)",
    "PEP 495 -- Local Time Disambiguation (the `fold` attribute)",
    "Python docs, 'naive and aware objects' (datetime module preamble)"
  ],
  "differential": "Do NOT report a naive `now()` whose result is only displayed to a human and never re-read: a `--debug` sys-info dump (coverage.py control.py:1413), a progress line, an exception message. Do NOT report `fromtimestamp()` used to render a file mtime for a human log line (coverage.py debug.py:235) -- converting an epoch to local wall time is the point there. Do NOT report a call already wrapped by a helper that re-attaches the zone: the naive `now()` inside `format_local_datetime(datetime.now())` is correct, and a rule matching the inner call alone will flag the project's own guarded twin. The discriminator is the DESTINATION, not the call. Severity drops to CONSIDER when the artifact has no in-repo reader and the exposure is limited to documented external consumers -- still a finding, because the schema is a contract.",
  "detected_by": null,
  "detectability": "implementable"
}
```

Implementation note for `scan_python_pitfalls.py`: the destination test is the whole rule. A cheap
first cut with good precision is *"naive `now()`/`fromtimestamp()` whose value reaches a `json.dump`
argument, a DB execute parameter tuple, or a dict literal assigned to a key matching
`time|stamp|when|date|created|modified`"*, minus anything lexically inside a call whose name matches
`format_.*datetime|.*_local_.*`. That would have found both coverage.py sites and none of the three
dismissals.

### 2. AMENDMENT — `zip-truncates-on-length-mismatch`

The current `differential` excludes only *provably equal-length* operands. It does not cover
**deliberate surplus**, which is what `report.py:106`/`:176` are, and which is a recognisably common
idiom (carrying a sort key or an internal id alongside the displayed columns). Append to
`differential`:

> Do NOT report when the longer operand carries a **deliberate surplus** the `zip` exists to drop —
> a row that appends a sort key, an internal id, or a raw numeric alongside its formatted twin, then
> zips against a shorter header/column list. The tell is a build site that appends one extra element
> unconditionally, after all the conditional blocks, and a consumer that indexes it by a negative or
> named constant (`column_order["cover"] = -1`). Here `strict=True` is not a fix but a crash: verify
> the surplus is *unintended* before proposing it. coverage.py `report.py:106,176` is the exemplar —
> `len(row) == len(header) + 1` in all four config combinations, by construction.

### Not proposed, with reasons

| Family | Why no shape |
|---|---|
| `S608` | 0/1 here, 0/1 on idlelib, and 1-of-5 recall on its own pattern within this file. Already covered by FP-taxonomy #46. |
| `PLW0127` | The only instance is the module-level builtin-capture idiom. Belongs in the FP taxonomy, not the shape catalog — entry drafted below. |
| `PLW3301` | No defect semantics. Recommend removing from tier 1. |
| `S302`, `S307` | Trust-boundary policy, not defect. Both correctly ACCEPTABLE in a tool whose job is executing user code. |

### Suggested FP-taxonomy addition

> **`PLW0127` on a module-level capture of a builtin.** *Looks like:* `open = open` flagged as a
> self-assignment. *Why it is not a bug:* the LHS binds a new **module global**; the RHS reads the
> **builtin**. The statement captures the builtin at import time so that later monkeypatching of
> `builtins.open` cannot break the module — coverage.py `python.py:30` states exactly that in a
> comment, and pairs it with `os = isolate_module(os)`. ruff's rule compares names without comparing
> scopes, so at module level a name that shadows a builtin is *never* a no-op.
> *Real bug:* a self-assignment where both sides resolve to the same binding — inside a function
> body, or at module level for a name that is not a builtin and is already a module global.
