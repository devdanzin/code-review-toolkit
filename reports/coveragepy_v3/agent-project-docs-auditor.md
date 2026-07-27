# project-docs-auditor — coverage.py @ `6b3259ab`

**Scope:** out-of-code documentation — `doc/`, `README.rst`, `CHANGES.rst`, `howto.txt`,
`pyproject.toml`, `setup.py`, `tox.ini`, `MANIFEST.in`, `CITATION.cff`.
Docstrings inside `coverage/` belong to documentation-auditor and are excluded except where a
docstring is the *source* of a generated out-of-code document.

**Did I edit the reviewed tree? NO.** All work was done on a `git archive` copy at `/tmp/covrepro`.
`/home/danzin/projects/coveragepy` was verified at the start and again mid-run: still
`6b3259abb64a3cb80b4800f58fe1c71b24970110`, still with only the same five pre-existing untracked
paths (`ctracer_repros/`, three `ctracer_review_*.md`, `repro.py`). The `/tmp` copy was deleted
out from under me part-way through by a concurrent process and re-extracted; the target was
re-verified intact at that point. Execution repros were run in `/tmp/cogcheck/`.

---

## 1. Inventory audited

| Surface | Files |
|---|---|
| Narrative docs | `doc/*.rst` — 26 files (api×6, branch, changes, config, contexts, contributing, dbschema, excluding, faq, howitworks, index, install, messages, migrating, other, plugins, sleepy, source, subprocess, trouble, whatsnew5x) |
| Command reference | `doc/commands/*.rst` — 12 files (11 command pages + index) |
| Man page | `doc/python-coverage.1.txt` — hand-maintained RST, 511 lines |
| Doc build | `doc/conf.py`, `doc/cog_helpers.py`, `doc/requirements.in/.pip`, `doc/dict.txt` |
| Root | `README.rst`, `CHANGES.rst`, `howto.txt`, `CONTRIBUTORS.txt`, `NOTICE.txt`, `LICENSE.txt`, `CITATION.cff` |
| Metadata | `pyproject.toml` (no `[project]` table — tool config only), `setup.py` (all packaging metadata), `tox.ini`, `MANIFEST.in`, `metacov.ini` |
| Absent | No `CONTRIBUTING.rst` at root (contributor docs live at `doc/contributing.rst`); no `CLAUDE.md` |

---

## 2. Catalogued findings — confirmed, not re-litigated

### CRF-COVPY-0056 `generated-doc-propagates-a-source-error` — **CONFIRMED, exact blast radius measured**

- **Source of truth:** `coverage/config.py:661-664` tries `.coveragerc.toml`, `setup.cfg`,
  `tox.ini`, `pyproject.toml` (after defaulting to `.coveragerc` at `:656-657`).
- **Erroneous source:** `coverage/cmdline.py:299-303` — *"By default '.coveragerc', 'setup.cfg',
  'tox.ini', and 'pyproject.toml' are tried."* `.coveragerc.toml` is omitted.
- **Blast radius, counted:** the wrapped help text appears in **10** cog-generated files —
  `doc/commands/cmd_{annotate,combine,debug,erase,html,json,lcov,report,run,xml}.rst` — plus an
  **11th, independent, hand-maintained copy** at `doc/python-coverage.1.txt:83-84`, which cog
  never touches.
- **Guarded twin:** `doc/config.rst:41-44` states the list **correctly**, including
  `.coveragerc.toml`. Its existence is what proves the other eleven wrong rather than merely
  differently worded.
- Regenerating cannot fix any of the ten; the fix is one string in `cmdline.py` plus a manual
  man-page edit.

### CRF-COVPY-0057 `implemented-but-undocumented-option` — **CONFIRMED**

Mechanical diff of `CoverageConfig.CONFIG_FILE_OPTIONS` (53 entries, extracted by AST) against the
`[section] name` headings in `doc/config.rst` (50):

- **In code, not documented:** `report:contexts` (`config.py:441`),
  `report:partial_branches_always` (`config.py:437`), `run:_crash` (`config.py:428`).
- `run:_crash` is underscore-prefixed and self-evidently private — **ACCEPTABLE**, not part of
  the finding. The other two are the catalogued pair.
- **Documented but not in code: zero.** No phantom options. That direction is clean.

### CRF-COVPY-0058 `process-marker-invisible-to-its-own-checklist` — **CONFIRMED, one extra site**

`howto.txt:23` says *'Edit supported Python version numbers. Search for "PYVERSIONS".'* Three
singular `PYVERSION` markers are invisible to that grep:

- `coverage/execfile.py:95` (catalogued)
- `coverage/phystokens.py:98` (catalogued)
- **`pyproject.toml:165`** — a `# PYVERSION` comment directly above `target-version = "py310"`.
  Not in the catalogued pair; adding it.

---

## 3. Generated-doc machinery (briefing item 4) — verified by execution

`cogapp` is not installed here, so I reimplemented cog's check (`/tmp/cogcheck/minicog.py`):
extract each `.. [[[cog … ]]] … [[[end]]]` block, exec the source with per-file persistent globals
and a stub `cog` module, and diff against the checked-in text. Two harness artifacts were
eliminated first (`sys.argv[0]` must be `__main__.py` for optparse's prog name, since
`cog_helpers.show_help` rewrites `__main__.py`→`coverage`; and the one-line `[[[cog … ]]]` form has
no separate mid-marker).

**Result: 39 blocks, 0 drift, 0 errors.** Every generated block in `doc/` is byte-identical to what
its source produces today.

**This is the finding, not the absence of one.** Because the generator is faithful and `tox.ini:85`
/ `:107` gate on `cog --check` in CI, *drift* is impossible — and therefore any error in the
**source** is permanently baked into every copy and **regeneration cannot fix it**. CRF-COVPY-0056
is one instance; N1 below is a second, previously unrecorded one. A "docs are in sync" green check
is not evidence the docs are correct.

**Sources, and what validates them:**

| Generated block | Source | Self-validating? |
|---|---|---|
| `show_help(cmd)` × 10 | live `coverage <cmd> --help` output | **No** — reproduces whatever the help strings in `cmdline.py` say |
| `show_configs(ini, toml)` × 10 | `read_coverage_config` on both syntaxes | **Partly** — see below |
| `dbschema.rst` × 2 | `sqldata.SCHEMA_VERSION`, `sqldata.SCHEMA` | Yes — printed straight from code |

**Gap in `show_configs` validation (checked, currently harmless).** `cog_helpers.py:81-89` reads
both the ini and toml forms and calls `cog.error` on any mismatch, and it passes `warn=cog.error`
into `read_coverage_config`. I tested what that actually catches:

- A bogus **option** in a real section → `"Unrecognized option '[run] branchh='"` → `cog.error` →
  the doc build fails. Good: every documented option name in every config example is machine-checked.
- A bogus **section** (`[runn]`) → **no warning, no exception, silently ignored.** A typo'd section
  name in a doc example would ship.

I then extracted every `[section]` / `[tool.coverage.section]` / `[coverage:section]` header from
all doc config examples and diffed against the seven real sections: **0 invalid**. So the hole is
latent, not live. Worth closing, but not a finding today.

---

## 4. Novel findings

### N1 — `--sort=branch` / `--sort=brpart` are documented unconditionally but fail under the default configuration
**CONSIDER** · shape `generated-doc-propagates-a-source-error` (second instance) · **reproduced**

- **Code:** `coverage/report.py:233-235` —
  `column_order = dict(name=0, stmts=1, miss=2, cover=-1)`, and only `if self.branches:` does it
  `update(dict(branch=3, brpart=4))`. `:259-261` raises `ConfigError` when the column is unknown.
- **Reproduced** (`/tmp/cogcheck/proj`, no `--branch`):
  ```
  $ coverage run prog.py && coverage report --sort=branch
  Invalid sorting option: 'branch'          # exit code 1
  $ coverage report --sort=brpart
  Invalid sorting option: 'brpart'          # exit code 1
  ```
  With `coverage run --branch`, both succeed. So two of the six documented values are valid only
  when branch coverage is enabled, and the docs say so nowhere.
- **Three doc copies, all wrong the same way:**
  - `coverage/cmdline.py:340-350` (the **source**) — *"Sort the report by the named column: name,
    stmts, miss, branch, brpart, or cover."* → cog-baked into `doc/commands/cmd_report.rst`
  - `doc/config.rst:890-892` — *"Allowed values are "Name", "Stmts", "Miss", "Branch", "BrPart",
    or "Cover"."*
  - `doc/python-coverage.1.txt:367-369` — same list, hand-maintained
- **Fix:** amend the `cmdline.py` help string (then `make prebuild`), plus the two hand-written
  copies. Alternatively make `report.py` raise a message naming the branch prerequisite — the
  current text gives the user no hint.

### N2 — the `+` sort prefix is accepted and documented nowhere; the `-` prefix is missing from two of three places
**CONSIDER** · shape `implemented-but-undocumented-option` · **reproduced**

`report.py:254-258` strips both a leading `-` (descending) and a leading `+` (ascending).
`coverage report --sort=+cover` runs and exits 0.

- `+` prefix: documented in **none** of the three places.
- `-` prefix: documented **only** at `doc/config.rst:892` (*"Prefix with `-` for descending sort"*).
  Omitted from `cmdline.py:340-350` (and so from `doc/commands/cmd_report.rst`) and from
  `doc/python-coverage.1.txt:367-369`.

`doc/config.rst` is the guarded twin — the project documents the prefix when it notices it.

### N3 — `doc/contexts.rst` omits `coverage json` from both context-reporting options
**CONSIDER** · **reproduced**

- `doc/contexts.rst:141-142` — *"The `coverage report` and `coverage html` commands **both**
  accept `--contexts` option…"*
- `doc/contexts.rst:145` — *"The `coverage html` command **also** has `--show-contexts`."*
- **Measured from the live parsers:** `--contexts` is accepted by `report`, `html` **and `json`**;
  `--show-contexts` by `html` **and `json`**. Confirmed functionally — `coverage json
  --show-contexts` emits a `contexts` key in the per-file output.
- **Guarded twin:** `doc/config.rst:1019-1025` documents `[json] show_contexts` properly. So the
  JSON reporter's context support is documented on the config page and denied on the contexts page.
- Note this is *not* CRF-COVPY-0010 (which is about `[report] contexts` being ignored by xml/lcov/
  annotate). Those three genuinely have no such option; `json` does, and works.

### N4 — `doc/config.rst` states the plugin limitation for `sysmon` but omits it for `pytrace`
**CONSIDER** · **reproduced**

- `coverage/core.py` sets `supports_plugins`: `:118` sysmon → `False`, `:124` ctrace → `True`,
  `:130` pytrace → **`False`**. `control.py:628-638` warns and disables the plugin for any core
  with `supports_plugins == False`.
- **Reproduced** with a probe plugin registering `add_file_tracer`:
  ```
  core=ctrace    (no warning)
  core=pytrace   CoverageWarning: Plugin file tracers (probeplugin.Probe) aren't supported with PyTracer
  core=sysmon    CoverageWarning: Plugin file tracers (probeplugin.Probe) aren't supported with SysMonitor
  ```
- **Docs:** `doc/config.rst:374-377` says sysmon *"does not yet support plugins, dynamic contexts,
  or some concurrency libraries."* `doc/config.rst:378` describes `pytrace` as *"the pure Python
  implementation of a sys.settrace function"* — **no limitation stated**, though it has the same one.
- **Guarded twin, in a different file:** `doc/install.rst:66-67` gets it right —
  *"A few features of coverage.py aren't supported without the C extension, such as concurrency and
  plugins."* (Without the C extension you get `pytrace`: `core.py:104-109`.) So the fact is
  documented on the install page and missing from the reference page.
- I initially hypothesised the constraint was unenforced on 3.14 (where sysmon is the default) —
  **that hypothesis is refuted**; `control.py:628` does warn. Recording the refutation so nobody
  re-derives it.

### N5 — `doc/contributing.rst` tells contributors to run tox environments that do not exist and target unsupported Pythons
**CONSIDER** (FIX if you weight new-contributor friction)

- `doc/contributing.rst:158-160`:
  ```
  To limit tox to just a few versions of Python, use the ``-e`` switch::

      $ python3 -m tox -e py38,py39
  ```
- `tox.ini:7` — `envlist = py3{10-15}, py3{14-15}t, pypy3, doc, lint, mypy`. There is no `py38` or
  `py39`. `setup.py` sets `python_requires=">=3.10"`.
- **Guarded twins in the same file:** `:59` (*"Ideally, use Python 3.10 (the lowest version
  coverage.py supports)"*), `:87` and `:176` (both `tox -e py310`). Only this one line is stale.
- **Dated:** the line was last touched by `4527c34f` (2023-06-18, *"docs: update commands for the
  move away from 3.7"*) and has survived two floor bumps since, including `5ef3ee6e` (2025-09-28,
  *"build: drop 3.9"*).

### N6 — the man page is the one user-facing document release automation never touches, and it has drifted in six independent ways
**CONSIDER** · systemic root, sites enumerated

`igor.py:357-394` (`do_edit_for_release`) rewrites `NOTICE.txt`, `CHANGES.rst` and `doc/conf.py`.
It does **not** touch `doc/python-coverage.1.txt`. That file's date field relies on an Emacs
`time-stamp` local variable (`doc/python-coverage.1.txt:502-509`), i.e. it only updates if a
maintainer opens the file in Emacs and saves. `howto.txt:31` carries a manual reminder —
*"Don't forget the man page: doc/python-coverage.1.txt"* — and the last real refresh commit is
literally titled *"docs: update the man page, for once"* (`2fd49618`, 2025-07-25).

Drift sites, all mechanically verified against the live optparse tables:

| # | Site | Drift |
|---|---|---|
| a | `:11` | `:Date: 2025-07-24`, but the file's own last content edit was `17b45a14` (2026-07-02, added `--keep-combined` in 6 places) and the latest release is 7.15.2 (2026-07-15). **344 days behind its own last edit.** |
| b | `:83-84` | `--rcfile` candidate list omits `.coveragerc.toml` (= CRF-COVPY-0056) |
| c | `:367-369` | `--sort` value list unconditional (= N1) and missing the `-`/`+` prefix (= N2) |
| d | `:417-419` | `--save-signal` omits *"Not available on Windows"*, which `cmdline.py:315` states |
| e | run section | `--module` long form absent; only `-m` is documented. `combine` section: `-a` short form absent; only `--append` is documented. (Every other long option on every command matches — see §5.) |
| f | `:465-484` | ENVIRONMENT section lists 4 vars; omits `COVERAGE_CORE` and `COVERAGE_PROCESS_START`, both user-facing and documented in `doc/config.rst` / `doc/subprocess.rst` |

Impact is indirect but real: `MANIFEST.in` ships the source in the sdist but setup.py never builds
it, so it is downstream distro packagers (Debian renames the binary to `python-coverage` — see
`tests/coveragetest.py:376`) who run `rst2man` on this and publish it as the system man page.

### N7 — `doc/install.rst` prints a `coverage --version` transcript the tool does not produce
**CONSIDER** · **reproduced**

`doc/install.rst:47-49`, `:79-81`, `:87-89` all show:

```
$ coverage --version
Coverage.py, version |release| with C extension
Documentation at |doc-url|
```

`conf.py:82` defines `|doc-url|` as the bare URL, so this renders as *"Documentation at
https://…"*. The actual second line, from `coverage/cmdline.py:780`, is
`"Full documentation is at {__url__}"`. Verified by execution:

```
Coverage.py, version 7.15.3a0.dev1 without C extension
Full documentation is at https://coverage.readthedocs.io/en/7.15.3a0.dev1
```

The adjacent sentence (*"The first line will either say 'with C extension,' or 'without C
extension.'"*) is correct — only the second line is wrong, in all three transcripts.

### N8 — `doc/index.rst` names 7.12.0 as the latest stable release
**CONSIDER** · latent (renders only in pre-release doc builds)

`doc/index.rst:25-27`, inside `.. ifconfig:: prerelease`:
*"The latest stable version is coverage.py 7.12.0, `described here`_."*

`conf.py:72-76` says `version = release = "7.15.2"`; 7.12.0 shipped 2025-11-18 and has been
superseded by 7.13.×, 7.14.× and 7.15.×. `conf.py:253` computes
`prerelease = bool(max(release).isalpha())`, so this block is invisible on a stable build and
**appears on the front page of the docs for any alpha/beta/rc build**. `howto.txt:27-29` has the
matching checklist item (*"IF PRE-RELEASE: — Version of latest stable release in doc/index.rst"*).

Being precise about the latency: the value was *correct* at the last pre-release (`7.12.1b1`,
which immediately followed 7.12.0). It is wrong relative to `main` today and will publish wrong at
the next pre-release unless the checklist step is performed. The `described here`_ link
(`doc/index.rst:30`) is also plain `http://` and unversioned, so it points at current docs rather
than the named release.

---

## 5. Directions checked and found **empty** — do not redo these

| Check | Method | Result |
|---|---|---|
| **CHANGES.rst vs git, last two releases** | `git log 7.15.0..7.15.1` and `7.15.1..7.15.2`, tag dates | **Clean.** Dates match tags exactly (7.15.2 → 2026-07-15, 7.15.1 → 2026-07-12, 7.15.0 → 2026-07-02). All 8 PRs claimed for 7.15.1 (2213/2214/2215/2216/2218/2220/2221/2224) are in the range. 7.15.2's claim that the regression came from pull 2215 in 7.15.1 is correct. Nothing user-visible landed unmentioned; the unmentioned commits are `chore:`/`docs:`/`test:`/`build:`. |
| **Config options, code → docs** | AST over `CONFIG_FILE_OPTIONS` vs `[sect] name` headings | 3 gaps, all catalogued (§2, CRF-COVPY-0057) |
| **Config options, docs → code** | same, reversed | **0 phantom options** |
| **CLI long options, code → man page** | live `optparse` tables vs parsed man sections | 1 gap (`run --module`) — N6e |
| **CLI short options, code → man page** | same | 1 gap (`combine -a`) — N6e |
| **CLI options, docs → code** | same, reversed | **0 phantom options** |
| **CLI commands** | 11 commands in `COMMANDS` | all 11 have a `doc/commands/cmd_*.rst` page **and** a man-page section |
| **cog block sync** | reimplemented cog check, 39 blocks | **0 drift, 0 errors** (§3) |
| **Config-example section names** | every `[…]` header in doc examples vs the 7 real sections | **0 invalid** |
| **Sphinx cross-references** | delegated: static extraction **plus** a real Sphinx 8.2.3 nitpicky build on a patched copy, live intersphinx, mutation-tested with 14 injected breakages | **0 broken.** 178 `:ref:`/183 labels, 1125 hyperlink refs, 27/27 anonymous refs, 3 substitutions, 156 Python-domain refs, 37 toctree entries, 3 directive file args, 6 `:file:`/path literals — all resolve. Build emitted **zero warnings**. |
| **Runtime deep links → doc anchors** | AST-classify every `slug=` by call target; normalise `doc/messages.rst` labels through `docutils.nodes.make_id` (`_`→`-`) | **0 broken, 0 orphaned.** 11 warn slugs → `#warning-<slug>` (`control.py:492`), 2 exception slugs → `#error-<slug>` (`cmdline.py:1188`); every one resolves, and every documented section has emitting code. *A naive hyphen-only regex reports all 15 as broken — the labels are spelled with underscores and docutils normalises them. Do not re-report that.* |
| **Environment variables, both directions** | regex over `getenv`/`environ` in `coverage/` vs all docs | **Effectively clean** — see triage below |
| **toctree completeness** | relative-path-resolved | 0 missing targets; 1 orphan (`whatsnew5x`) which correctly declares `:orphan:` at line 4 |
| **`[run] core` values** | `ctrace`/`sysmon`/`pytrace` vs `core.py:104-130` | all 3 exist |
| **`--concurrency` values** | man page + `config.rst` vs `CONCURRENCY_CHOICES` | exact match (`eventlet, gevent, greenlet, multiprocessing, thread`); the CLI help is *generated* from the set, so it cannot drift |
| **`coverage debug` topics** | man page list vs `cmdline.py:1067-1103` | exact match (`config, data, sys, premain, pybehave, sqlite`) |
| **`--save-signal` values** | `USR1`/`USR2` vs `cmdline.py:311` `choices=` | match (only the Windows caveat is dropped in the man page — N6d) |
| **`dynamic_context` values** | `test_function`, `none` vs `control.py:578-584` | match |
| **`[paths]` section** | `doc/config.rst:601+` vs `config.py:354-357` | handled and documented |
| **`version_info` contract** | `doc/api_module.rst:14-21` vs `coverage/version.py:11,24` | correct — 5 elements, `releaselevel` ∈ {alpha, beta, candidate, final} |
| **Public API surface** | `coverage/__init__.py` re-exports vs `doc/api_*.rst` | all 10 public names documented; the API pages use `autoclass`/`automodule`, so they cannot go stale by construction |
| **Extras** | `toml` (`setup.py:190`) | documented at `doc/config.rst:48` |

**Env var triage (all four apparent gaps dismissed with reasons):**

- `COVERAGE_ONE_CORE`, `COVERAGE_TEST_CORES` — named in `doc/contributing.rst:203,208`, read by
  `igor.py:125,131` and `tox.ini:31`. Not read by `coverage/` because they are test-harness vars.
  **Correct as documented.**
- `COVERAGE_OPTIONS`, `COVERAGE_STORAGE` — appear **only** in `doc/changes.rst:1664` and `:550`, as
  records of their *removal* (*"is no longer supported"*). Per FP class 44, a changelog entry is a
  historical record, not a reference. **Not phantoms.**
- `COVERAGE_FORCE_CONFIG` (`config.py:724`) is undocumented but self-labelled in the code as
  *"a secret environment variable"* for benchmarking. **POLICY at most, and already marked.**
- The remaining undocumented reads (`COVERAGE_COVERAGE`, `COVERAGE_TESTING`, `COVERAGE_DEBUG_CALLS`,
  `COVERAGE_SYSMON_LOG`, `COVERAGE_SYSMON_STATS`, `COVERAGE_TRACK_ARCS`) are internal debug/test
  switches. `COVERAGE_PROCESS_CONFIG` is absent from `doc/*.rst` but **is** published, via the
  `process_startup` docstring (`control.py:1443-1444`) rendered by `.. autofunction::` in
  `doc/api_module.rst:36`. Not a finding.

**Also checked and deliberately not reported:**

- `doc/python-coverage.1.txt` documents a command named `python-coverage`, which `setup.py` never
  installs (`console_scripts` are `coverage`, `coverage3`, `coverage-3.N`). This is the Debian
  rename — `tests/coveragetest.py:376` cites the exact Debian patch
  (`02.rename-public-programs.patch`). The man page is a `.txt`, not in any toctree, and never
  reaches readthedocs. **ACCEPTABLE.** Noting it so it isn't raised as an
  idlelib-CRF-0038-style finding next pass.
- `coverage3` / `coverage-3.N` entry points are mentioned only in `doc/changes.rst:1914`, but
  `main_deprecated` (`cmdline.py:1200-1211`) prints a deprecation banner on every invocation, so
  they are self-discoverable. **ACCEPTABLE.**
- `doc/faq.rst:74-79` explains a Python 3.7-vs-3.8 decorator reporting difference. Both versions
  are below the 3.10 floor, so the situation it describes can no longer arise. Harmless history
  rather than a misleading claim. **ACCEPTABLE** — flagging only so it is a conscious decision.
- `setup.py:65-77` classifies Python 3.16 as supported, while `README.rst:29` / `doc/index.rst:21`
  say *"3.10 through 3.15 beta"* and `tox.ini:7` / CI test through 3.15. Forward-declaring a
  classifier ahead of the test matrix is normal practice for this project. **ACCEPTABLE.**
- There is no plugin API version constant anywhere in `coverage/` — nothing to cross-check.
- `coverage/plugin.py`'s module docstring documents 3 of the 4 registration methods
  (`add_file_tracer`, `add_configurer`, `add_dynamic_context`; `add_noop` at
  `plugin_support.py:94` is absent). That docstring is autodoc'd into `doc/api_plugin.rst`, but it
  is an in-code docstring — **handing to documentation-auditor**, not claiming it here.

---

## 6. Recommendations, prioritised

1. **N1** — fix the `--sort` value list in `cmdline.py:340-350`, run `make prebuild`, and hand-edit
   `doc/config.rst:890-892` and `doc/python-coverage.1.txt:367-369`. This is a documented option
   value that exits 1 under the default configuration; of everything here it is the only one that
   makes a user's command fail.
2. **CRF-COVPY-0056** — one-line fix in `cmdline.py:299-303` + `make prebuild` clears 10 files;
   the man page needs a separate manual edit.
3. **N5** — `doc/contributing.rst:160` → `py310,py311` (or any real env). Cheapest fix, highest
   new-contributor friction.
4. **N6** — decide whether the man page stays hand-maintained. If it does, it needs a CI check;
   `tox.ini` already gates `doc/*.rst` on cog but `doc/python-coverage.1.txt` is a `.txt` and is
   matched by nothing. Six independent drifts in one file is a process signal, not six mistakes.
5. **N3, N4** — two-sentence doc edits; both have a correct twin elsewhere in `doc/` to copy from.
6. **CRF-COVPY-0057** — document `[report] contexts` and `[report] partial_branches_always`, or
   mark them private the way `_crash` is.
7. **N7, N8, N2** — cosmetic/latent. N8 is worth doing before the next pre-release, since that is
   exactly when it becomes visible on the front page.
8. **CRF-COVPY-0058** — spell the three singular markers `PYVERSIONS`, or widen the `howto.txt`
   instruction to `PYVERSION`.
9. **Process, not a finding:** consider having `show_configs` reject unknown section names
   (§3) and narrowing `nitpick_ignore_regex` in `doc/conf.py:143-145`, which currently suppresses
   *any* unresolvable `py:class` of the form `coverage.X.Y` — proven by injection, no live
   breakage hidden today.
