# architecture-mapper — coverage.py

**Target:** `/home/danzin/projects/coveragepy/coverage` @ `6b3259abb64a3cb80b4800f58fe1c71b24970110` (main, 2026-07-26)
**Scope:** 44 Python files / 16,426 lines + 9 C files in `coverage/ctracer/`. Target tree **not modified**.
**Inputs:** `analyze_imports.json` (resolution `ok`, 39 graph nodes, 9 cycles), `measure_complexity.json` (698 functions, 14 hotspots).

---

## 60-second summary

coverage.py is a **strictly layered core with a pluggable rim**. Six leaf modules carry no internal
imports at all; one god module (`control.py`, fan-out 27, 1510 lines) wires everything; and three
independent *backend families* hang off well-defined seams — tracer cores, report formats, config
parsers. The layering is genuinely clean: **there is not one layering inversion in the runtime
import graph.** Every apparent inversion is a deliberate function-level import.

The structural risk is not the layering, it is the **seams**. All three seams are `Protocol`s that
specify only the narrowest common denominator, and the drivers reach past them — `Collector` probes
its tracer with seven `hasattr()` calls (`collector.py:260-273`) and `report_core.Reporter`
mandates exactly two members (`report_core.py:23-29`). Every cross-cutting concern therefore lives
*inside* each backend, and **19 of the 31 concerns I inventoried are implemented by some backends
and not others.** That is the `one-concern-implemented-per-backend` shape, and it is the dominant
defect generator in this codebase.

**Of the 9 cycles, 6 are artefacts, 1 is real-but-load-bearing-on-CPython, and 2 share a single
one-line root** (`from coverage import __version__` at `jsonreport.py:14` and `xmlreport.py:16`),
whose guarded twin sits in the same file (`xmlreport.py:22`).

---

## 1. Layer diagram

Arrows point *downward only*. `⇢` = TYPE_CHECKING-only. `⤳` = deliberate function-level (late) import.

```
 L8  ENTRY          __main__.py    cmdline.py(1211L)    __init__.py [facade]    pth_file.py [template, not imported]
      │                  │              │                    │
 L7  ORCHESTRATION       └──────────────┴───► control.py (1510L, fan-out 27)  ◄⤳► patch.py   ◄⤳ multiproc.py
                                                  │
        ┌─────────────────────────────────────────┼─────────────────────────────────────────┐
        ▼                                         ▼                                         ▼
 L6  REPORTING                            L5  MEASUREMENT                          L4  DATA
     report_core.py [driver]                  collector.py [driver]                    data.py [facade]
       ├ report.py  (text/md/total)             core.py [backend selector]               └ sqldata.py
       ├ html.py (872L)                           ├ pytracer.py                              └ sqlitedb.py
       ├ xmlreport.py                             ├ sysmon.py                                    │
       ├ jsonreport.py                            └ ctracer/*.c  [C ext]                         │
       ├ lcovreport.py                          inorout.py [should-trace policy]                 │
       └ annotate.py                            execfile.py                                      │
        │                                         │                                              │
        ▼                                         ▼                                              ▼
 L3  DOMAIN        results.py    python.py ◄⤳► parser.py    config.py ◄──► tomlconfig.py    numbits.py
                                                 │
 L2  PUBLIC API    plugin.py (fan-in 15, third-party contract)    plugin_support.py    regions.py
                                                 │
 L1  PRIMITIVES    misc.py   files.py   debug.py   disposition.py   context.py   bytecode.py   phystokens.py
                                                 │
 L0  FOUNDATION    types.py(29)   exceptions.py(23)   env.py(13)   version.py(6)   templite.py   numbits.py
                   ── zero internal runtime imports (types.py has one ⇢ to plugin.py) ──
```

**Reading the graph.** `control.py` imports 27 internal modules and is imported by 3
(`__init__.py:24`, `cmdline.py:23`, `patch.py:105`⤳). It is the only place the four subsystems meet.
Everything else is a tree.

**The facade's fan-in is misleading.** `coverage/__init__.py` shows fan-in 14, but the composition is:

| kind | count | sites |
|---|---|---|
| `⇢` TYPE_CHECKING `from coverage import Coverage` | 9 | `annotate.py:20`, `html.py:41`, `jsonreport.py:20`, `lcovreport.py:19`, `patch.py:17`, `python.py:25`, `report.py:21`, `report_core.py:20`, `xmlreport.py:25` |
| `⤳` late, inside a function body | 3 | `control.py:1364`, `debug.py:214`, `multiproc.py:34` |
| not imported at all (source template) | 1 | `pth_file.py:12` |
| **genuine top-level binding from the facade** | **2** | **`jsonreport.py:14`, `xmlreport.py:16`** |

The 13 `from coverage import env` sites resolve to `coverage/env.py`, not the facade — the analyzer
indexed them correctly this run (briefing FP class 31 is not in play for those).

---

## 2. Cycle table — the 9 cycles

| # | Ring | Closing edge | Nature | Verdict | Module that breaks it |
|---|---|---|---|---|---|
| **4** | `__init__ → control → jsonreport → __init__` | `jsonreport.py:14` `from coverage import __version__` (top level; `__version__` **is** bound in `__init__.py:19-22`) | **Real, order-sensitive.** Works only because `__init__.py` binds `__version__` at :19 *before* importing `control` at :24. Swapping those two blocks — a change no reviewer would flag — raises `ImportError` at import time. | **FIX** | `jsonreport.py:14` → `from coverage.version import __version__`. **The twin already exists**: `sqldata.py:34` does exactly that. |
| **6** | `__init__ → control → xmlreport → __init__` | `xmlreport.py:16` `from coverage import __version__, files` | Same root as #4. `files` is a submodule bind (benign); `__version__` is the real edge. **Strongest twin in the codebase: the same file imports its sibling constant the safe way four lines later** — `xmlreport.py:22` `from coverage.version import __url__`. | **FIX** | `xmlreport.py:16` → split: `from coverage.version import __version__` + `from coverage import files`. |
| **2** | `config ↔ tomlconfig` | `config.py:21` (top) ⟷ `tomlconfig.py:13` `from coverage import config, env` (top) | **The only genuine mutual top-level cycle.** Both edges are import-time. It resolves only via CPython's ≥3.7 `_handle_fromlist` fallback to `sys.modules` for a partially-initialised submodule. Load-bearing on interpreter behaviour, not on the project's own ordering. | **CONSIDER** | `tomlconfig` uses exactly **two** names from `config`: `process_file_value` (`tomlconfig.py:187` → `config.py:610`) and `process_regexlist` (`tomlconfig.py:202` → `config.py:623`). Move those two free functions to `misc.py` and the cycle disappears. |
| 1 | `__init__ → data → sqldata → sqlitedb → debug → __init__` | `debug.py:214` `import coverage` inside `short_filename()` | Deliberate late import; only to get `os.path.dirname(coverage.__file__)` for a debug path prefix. | ACCEPTABLE | Already broken at runtime. Removable entirely: `debug.py` can use its own `__file__`. |
| 3 | `parser ↔ python` | `parser.py:93` `from coverage.python import get_python_source` inside `PythonParser.__init__` | Deliberate late import. `python.py:18` imports `parser` at top level; the reverse is deferred. | ACCEPTABLE | Already broken. |
| 5 | `__init__ → control → __init__` | `control.py:23` (`env` submodule) + `control.py:1364` late `import coverage as covmod` inside `sys_info()` | Facade artefact + late import. | ACCEPTABLE | n/a |
| 7 | `__init__ → control → multiproc → __init__` | `multiproc.py:34` `from coverage import Coverage` inside `_bootstrap()`, **carrying the comment `# avoid circular import`** | Deliberate, self-documented. | ACCEPTABLE | Already broken. |
| 8 | `__init__ → control → html → __init__` | `html.py:20` plain `import coverage` (top level) | `import pkg` binds only the module object; the attribute read is deferred to `html.py:319` (`coverage.__version__`). No import-time dependency on the facade being complete. | ACCEPTABLE | n/a — but see §5, `html.py:42`. |
| 9 | `control ↔ patch` | `patch.py:105` `from coverage.control import _after_fork_in_child` inside `_patch_fork()` | Deliberate late import. | ACCEPTABLE | Already broken. |

### The version-import inconsistency, in one place

Four different idioms for the same need, in the same package:

| idiom | sites | cycle? |
|---|---|---|
| `from coverage.version import __version__` | `sqldata.py:34` | no ← **the twin** |
| `from coverage.version import __url__` | `control.py:70`, `html.py:38`, `xmlreport.py:22`, `cmdline.py:30` | no |
| `import coverage` + `coverage.__version__` at runtime | `html.py:20` + `html.py:319` | no (deferred) |
| `from coverage import __version__` | `jsonreport.py:14`, `xmlreport.py:16` | **yes, order-sensitive** |

This is one systemic root with two sites, not two findings.

---

## 3. Backend × concern matrices — the headline

### 3a. Tracer cores (`PyTracer` / `CTracer` / `SysMonitor`)

**Seam:** `types.Tracer` Protocol, `types.py:86-114` — 9 attributes + 5 methods.
**Selector:** `core.py:104-134` sets `tracer_class`, `supports_plugins`, `packed_arcs`, `systrace`.
**Driver:** `Collector._start_tracer()`, `collector.py:249-278`.

The seam is not enforced. Six attributes are set unconditionally (`collector.py:252-258`); **seven
more are installed behind `hasattr()` probes** (`collector.py:260-273`). A backend "supports" a
concern by merely *having an attribute name*. Nothing checks the set is coherent.

| # | Concern | Driver site | PyTracer | CTracer | SysMonitor |
|---|---|---|---|---|---|
| 1 | `data` / `trace_arcs` / `should_trace` / `should_trace_cache` | `collector.py:252-257` | ✅ `pytracer.py:82-85` | ✅ `tracer.h:21-27` | ✅ `sysmon.py:192-195` |
| 2 | `lock_data` / `unlock_data` | `collector.py:253-254` | ✅ used `:232,:237` | ✅ used `tracer.c:492,:531` | ✅ used `sysmon.py:352,:357` |
| 3 | **`warn` — settrace-hijack detection** | `collector.py:258` | ✅ **only backend that calls it**, `pytracer.py:352-358` | ❌ member declared `tracer.c:1055`, **never referenced** outside dealloc | ❌ declared `sysmon.py:203` under `# TODO: warn is unused.` (`:202`) |
| 4 | `concur_id_func` (greenlet/eventlet/gevent) | `collector.py:260-261` | ❌ | ✅ `tracer.c:220,:240` | ❌ (refused up front, `core.py:79-80`) |
| 5 | `file_tracers` (plugin file tracers) | `collector.py:262-263` | ❌ | ✅ `tracer.c:517` | ❌ |
| 6 | `check_include` | `collector.py:266-267` | ❌ | ✅ `tracer.c:464` | ❌ |
| 7 | `disable_plugin` | `collector.py:272-273` | ❌ | ✅ `tracer.c:600-606` | ❌ |
| 8 | `supports_plugins` | `core.py:118,:124,:130` | False | True | False |
| 9 | **dynamic contexts** (`should_start_context`/`switch_context`) | `collector.py:268-271` | ✅ `pytracer.py:190-196,:306-309` | ✅ `tracer.c:344-359,:789` | ❌ attrs exist `sysmon.py:198-199` under `# TODO: ... are unused!` (`:196`); guarded by `core.py:77-78` |
| 10 | **`threading` attr / per-thread install** | `collector.py:264-265,:334,:371-375` | ✅ `pytracer.py:93,:320-322,:338-345` | ❌ no `threading` member anywhere in `ctracer/` | ❌ (process-global `sys.monitoring` instead) |
| 11 | **`systrace` → `threading.settrace` hook** | `collector.py:334,:371` | True | True | **False** — the installation trace is skipped |
| 12 | **`post_fork`** | `collector.py:377-381` | ❌ | ❌ | ✅ `sysmon.py:300-302` |
| 13 | packed arcs (bit-packed int pairs) | `core.py:119,:125,:131`; unpacked `collector.py:469-479` | False | **True** | False |
| 14 | `get_stats` | `types.py:113` | returns `None` always, `pytracer.py:368-370` | compile-gated `#if COLLECT_STATS`, `tracer.c:1026-1044` | env-gated `COVERAGE_SYSMON_STATS`, `sysmon.py:53,:312-314` |
| 15 | **`activity` flag memory model** | `collector.py:389`, `:190` | plain bool `pytracer.py:112` | **`_Atomic BOOL`** `tracer.h:39`, `tracer.c:852` | plain bool `sysmon.py:233` |
| 16 | own internal lock | — | ❌ | ❌ | ✅ `self.lock` `sysmon.py:224` (distinct from the collector's `data_lock`) |
| 17 | `atexit` hook | — | ✅ `pytracer.py:116` | ❌ | ❌ |
| 18 | runtime `__annotate__` filtering | — | ❌ | ❌ | ✅ `sysmon.py:323-325` |
| 19 | re-reads source from disk while measuring | — | ❌ | ❌ | ✅ `sysmon.py:489-503` |

**11 of 19 concerns are present in only one or two of three backends.** Concerns 3, 10, 11, 12, 15
are the ones where the *absence* is silent — the backend has no attribute, `hasattr` returns False,
and the collector proceeds as if the concern were handled.

Three concerns deserve naming as design gaps rather than bugs-in-a-backend:

- **`warn` (3) is a one-backend concern.** The Protocol declares it (`types.py:97`); the driver
  installs it on all three (`collector.py:258`); only `PyTracer` ever calls it. A `sys.settrace`
  hijack is therefore invisible on the default core.
- **`post_fork` (12) is a one-backend concern in the opposite direction.** Only `SysMonitor`
  defines it. The `hasattr` probe at `collector.py:380` silently no-ops for the other two.
- **`threading`/`systrace` (10, 11)** is the one place the three backends have *genuinely
  different* semantics rather than a missing feature — `sys.monitoring` is process-global, so it
  needs no per-thread install. The divergence is legitimate; what is not is that it is expressed as
  a bare boolean (`core.py:120,:126,:132`) consumed at two unrelated sites
  (`collector.py:334`, `:371`) with no comment saying why.

### 3b. Report formats (6 backends)

**Seam:** `report_core.Reporter` Protocol, `report_core.py:23-29` — **two members**: `report_type`
and `report(morfs, outfile) -> float`.
**Shared driver:** `get_analysis_to_report()`, `report_core.py:71-123`; `render_report()`, `:32-68`.

| Concern | Shared? | text `report.py` | html | xml | json | lcov | annotate |
|---|---|---|---|---|---|---|---|
| include/omit filtering | ✅ `report_core.py:85-91` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `ignore_errors` on unparseable file | ✅ `report_core.py:110-121` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| output-file lifecycle | ⚠️ `render_report` `:32-68` | ❌ own (`control.py:1167`) | ❌ own dir mgmt | ✅ `control.py:1289` | ✅ `:1327` | ✅ `:1356` | ❌ own multi-file |
| conforms to `Reporter` (`report_type`) | — | ❌ | ❌ | ✅ `xmlreport.py:60` | ✅ `jsonreport.py:37` | ✅ `lcovreport.py:162` | ❌ |
| **`[report] contexts`** | ❌ | ✅ `report.py:209` | ✅ `html.py:132` | ❌ | ✅ `jsonreport.py:79` | ❌ | ❌ |
| **`skip_covered`** | ❌ | ✅ `report.py:280,:300` | ✅ `html.py:289-291,:451` | ❌ | ❌ | ❌ | ❌ |
| **`skip_empty`** | ❌ | ✅ `report.py:284,:303` | ✅ `html.py:292-294,:459` | ✅ `xmlreport.py:176` | ❌ | ✅ `lcovreport.py:207` | ❌ |
| **`precision`** | ❌ | ✅ `report.py:47` | ✅ `html.py:349` | ❌ own rounding `xmlreport.py:33-38` | ✅ `jsonreport.py:42` | ✅ `lcovreport.py:167` | ❌ |
| **regions (functions/classes)** | partly `results.AnalysisNarrower` | ❌ | ✅ `html.py:600-607` | ❌ | ✅ `jsonreport.py:143-153` | ⚠️ functions only `lcovreport.py:83-92` | ❌ |
| `show_contexts` | ❌ | ❌ | ✅ | ❌ | ✅ | ❌ | ❌ |
| **returns a total → `--fail-under` applies** | `cmdline.py:892-947` | ✅ `:894` | ✅ `:906` | ✅ `:916` | ✅ `:922` | ✅ `:929` | ❌ **`:904` never sets `total`** |
| `sort` | ❌ | ✅ `report.py:252-266` | client-side JS | ❌ | ❌ | fixed `lcovreport.py:185` | ❌ |
| per-format skip override (`html_skip_*`) | ❌ | ❌ | ✅ `html.py:289-294` | ❌ | ❌ | ❌ | ❌ |

**Only 2 of 13 concerns are actually shared.** The two that are (`include/omit`, `ignore_errors`)
are exactly the two that live in `report_core.get_analysis_to_report()` — which is the proof that
the driver *could* own the rest.

Two structural notes for downstream agents:

- **`annotate` is the runt backend.** It has 2 of 13 concerns. `control.py:1190-1198` accepts and
  installs `report_contexts` into `override_config` — and `AnnotateReporter` never reads it
  (`annotate.py` has no `set_query_contexts` call). It is the only report command with no `total`,
  so `--fail-under` silently does nothing for `coverage annotate`.
- **`contexts` is stateful, not parameterised.** The three backends that honour it do so by calling
  `CoverageData.set_query_contexts()` (`sqldata.py:1001-1020`), which mutates the *shared*
  `CoverageData`. `sqldata.py:1019-1020` only clears `_query_context_ids` when called with a falsy
  value. A programmatic caller that runs `cov.report(contexts=[...])` and then `cov.xml_report()`
  gets the second report silently filtered by the first report's contexts.

### 3c. Config parsers (INI vs TOML) — 2 backends

**Seam:** `TConfigParser = HandyConfigParser | TomlConfigParser` — a bare union, `config.py:146`.
Not a Protocol; conformance is unchecked.
**Dispatch:** by file extension, `config.py:308-314`.

| Concern | INI (`HandyConfigParser`) | TOML (`TomlConfigParser`) |
|---|---|---|
| `$VAR` substitution on scalar values | ✅ `config.py:107` | ✅ `tomlconfig.py:123` |
| `$VAR` substitution on regex lists | ✅ (via `get`) | ✅ `tomlconfig.py:193` |
| **`$VAR` substitution on plugin option sections** | ✅ (routes through `get`, `config.py:107`) | ❌ `get_section` returns raw data, `tomlconfig.py:146-148` |
| **plugin name containing a dot** | ✅ flat section name | ❌ `real_section.split(".")` at `tomlconfig.py:91` turns `foo.bar` into a nested table path |
| `our_file` prefix handling | flat | `tool.coverage.` prefix, `tomlconfig.py:86-89` |
| unreadable-file signalling | shared caller `config.py:296-320` | shared caller |

The divergence is structural: **INI funnels every read through one `get()` that applies
substitution; TOML has three independent read paths (`get`, `get_section`, `getlist`) and applies
substitution in two of them.** Any new option type added to TOML will inherit the gap.

### 3d. Data storage — 2 sub-backends behind one class

Not separate classes: `CoverageData` (`sqldata.py:146`) switches on a single flag.

| Concern | on-disk | in-memory (`no_disk=True`) |
|---|---|---|
| filename choice | `sqldata.py:289-298` | `:291` short-circuit |
| `erase` | ✅ guarded `sqldata.py:881` | ✅ guarded `:894` |
| **`write()`** | ✅ | ⚠️ `sqldata.py:912-929` has **no `no_disk` guard** where its siblings do |
| per-thread connection | `self._dbs[threading.get_ident()]`, `sqldata.py:317,:456` | same |
| dead-thread reaping | `_reap_dead_thread_dbs`, `sqldata.py:373-395` | same code path, different consequence |

`control.py:1082` constructs a second, in-memory `CoverageData` for `[paths]` remapping — so both
sub-backends can be live in one process.

### 3e. `FileReporter` — 3 implementations of one interface

**Seam:** `plugin.FileReporter`, `plugin.py:379-614` — **14 public methods.**

| Implementation | methods | note |
|---|---|---|
| `PythonFileReporter` (`python.py`) | 14 + `should_be_python()` | the reference implementation |
| third-party plugin subclasses | 14 (base raises `_needs_to_implement`) | the public contract |
| `DebugFileReporterWrapper` (`plugin_support.py:243-297`) | **10** | hand-mirrored; missing `missing_arc_description`, `arc_description`, `code_regions`, `code_region_kinds` |

`report_core.py:110` calls `fr.should_be_python()` — a method only `PythonFileReporter` has, invoked
through the base type, with a `# type: ignore[attr-defined]` acknowledging it.

---

## 4. Blast-radius ranking (for the other agents)

Raw fan-in over-weights type-only modules. Ranked by *semantic* blast radius — how many dependents
would be behaviourally wrong if the module were wrong:

| Rank | Module | fan-in | LOC | Why it is the blast radius |
|---|---|---|---|---|
| **1** | **`files.py`** | 10 | 585 | Owns *path identity*. Every "is this the same file" decision — measurement, reporting, combining, omit/include, `[paths]` remapping — funnels through `canonical_filename`/`abs_file`/`PathAliases`. A wrong answer here is silent and produces 0% coverage, not an error. Dependents: `inorout`, `python`, `report_core`, `annotate`, `html`, `control`, `plugin`, `data`, `xmlreport`, `execfile`. |
| **2** | **`control.py`** | 3 | **1510** | fan-out **27**. The only module where all four subsystems meet; every agent will end up here. `Coverage.report/html_report/xml_report/json_report/lcov_report/annotate` (`:1088`-`:1356`) are six near-duplicate methods differing in which `override_config` keys they pass. |
| **3** | **`results.py`** | 9 | 502 | Owns all coverage *arithmetic* — `Numbers`, `Analysis`, `display_covered` (`:403`), `should_fail_under` (`:483`). Every report backend and the CLI gate depend on it. Wrong arithmetic is silent. |
| **4** | **`sqldata.py`** | 1 | 1209 | fan-in 1 is deceptive — everything reaches it through the `data.py` facade (fan-in 7). It is the only durable artefact the whole product produces, and it is concurrent (per-thread connections, `:317`, `:456`). |
| **5** | **`misc.py`** | 22 | 382 | Highest true runtime fan-in. Mostly low-risk helpers (`isolate_module`, `human_sorted`), but `Hasher` and `substitute_variables` are semantic. Note `from coverage.exceptions import *` at `:28` — a deliberate 6.0-era re-export, documented at `:25-27`. |
| **6** | **`plugin.py`** | 15 | 617 | Third-party contract. Blast radius is *outside* the repo: a change breaks published plugins. POLICY risk, not defect risk. |
| **7** | **`inorout.py`** | 1 | 654 | fan-in 1 (`control.py:41`) but it *is* the should-trace policy — `InOrOut.should_trace` (`:343-443`, nesting 4) is the gate every measured line passes. |
| — | `types.py` (29), `exceptions.py` (23), `env.py` (13) | high | small | **De-prioritise.** `types.py` is annotations only (one `⇢` edge); `exceptions.py` is 10 class statements; `env.py` is computed constants with zero internal imports. High fan-in, near-zero defect surface. |

---

## 5. Structural issues

### FIX
- **`jsonreport.py:14` / `xmlreport.py:16`** — `from coverage import __version__` closes an
  order-sensitive import cycle through the package facade. Guarded twin in the same file at
  `xmlreport.py:22` and in `sqldata.py:34`. One-line fix at two sites.
- **`html.py:42`** — `if TYPE_CHECKING: from coverage.plugins import FileReporter`. **`coverage.plugins`
  does not exist** (the module is `coverage.plugin`). Still present at this commit. Because it is
  TYPE_CHECKING-only it never raises at runtime, and because the name is unresolvable mypy degrades
  every annotation using it to `Any` — the module's `FileReporter` annotations check nothing.
  *(= CRF-COVPY-0018, confirmed still live.)*

### CONSIDER
- **`config.py ↔ tomlconfig.py`** — the only genuine mutual top-level import. Breakable by moving
  `process_file_value` (`config.py:610`) and `process_regexlist` (`config.py:623`) into `misc.py`;
  they are the only two names crossing the boundary (`tomlconfig.py:187,:202`).
- **The `hasattr`-probed tracer seam** (`collector.py:260-273`). Seven optional capabilities with
  no declaration of which backend has which. `core.py` already carries three explicit capability
  flags (`supports_plugins`, `packed_arcs`, `systrace`, `:118-132`) — the guarded-twin pattern for
  the other seven exists inside the same file. Promoting the probes to explicit `Core` flags would
  make every gap in §3a visible at the selector instead of silent at the call site.
- **The `Reporter` Protocol under-specifies** (`report_core.py:23-29`). Three of six backends do not
  satisfy it (`report.py`, `html.py`, `annotate.py` have no `report_type`), which is why three of
  six bypass `render_report`. Nothing type-checks this because `control.py` calls the concrete
  classes directly.
- **`DebugFileReporterWrapper` mirrors 10 of 14 methods** (`plugin_support.py:243-297`). A
  hand-written wrapper over an interface that grew (regions were added later) will keep drifting.

### ACCEPTABLE (do not report as findings)
- All six late-import cycles (#1, #3, #5, #7, #8, #9). Each closing edge is inside a function body;
  `multiproc.py:34` even carries the rationale as a comment.
- `from coverage import env` at 13 sites — submodule bind, briefing FP class 31.
- `from coverage.exceptions import *` at `misc.py:28` — documented backward-compat re-export
  (`misc.py:25-27`).
- `pth_file.py` unimported — it is a source template embedded into the installed `.pth` by
  `setup.py` (briefing FP class 34).
- `coverage/__main__.py` unimported — that is what `python -m coverage` is for.
- `import __pypy__` / `greenlet` / `eventlet` / `gevent` in `collector.py:127-141` — the only four
  external dependencies in the whole package, all conditional and all in one `try` block.

---

## 6. Look here first

For agents picking a starting point, in priority order:

1. **`collector.py:249-278` + `core.py:104-134` + `types.py:86-114`** — the tracer seam. Read all
   three together; §3a's matrix is derived from them. Any concern in that matrix with a ❌ in one
   column and ✅ in another is a candidate `one-concern-implemented-per-backend` finding.
2. **`report_core.py:23-29,:71-123` + the six reporters' first 60 lines** — the report seam. §3b's
   11 unshared concerns are the hunting ground. `annotate.py` (2 of 13 concerns) is the highest-yield
   single file.
3. **`files.py`** — highest semantic blast radius. `canonical_filename` (`:65`), `abs_file` (`:156`),
   `prep_patterns` (`:200`), `PathAliases` (`:416-551`).
4. **`control.py:1088-1356`** — six near-duplicate report entry points. Diff them against each other;
   the differences *are* §3b's matrix, and each asymmetry is either intentional or a bug.
5. **`sqldata.py:710-884` (`update`) and `:373-395` (`_reap_dead_thread_dbs`)** — the two most
   concurrency-sensitive regions in the data layer, both already carrying catalogued findings.
6. **`tomlconfig.py:85-95, :140-152, :185-205`** — the three independent read paths where the TOML
   backend diverges from INI.
7. **Complexity hotspots that sit *on* a seam** (from `measure_complexity.json`; 14 functions ≥5.0,
   avg 1.3):
   - `pytracer.py::PyTracer._trace:147` — 123 lines, nesting 5, **rank 1**. The whole PyTracer
     backend in one function.
   - `sysmon.py::SysMonitor.sysmon_py_start:317` — 66 lines, **nesting 6** (deepest in the project).
   - `inorout.py::InOrOut.should_trace:343` — 63 lines, nesting 4. The should-trace gate.
   - `html.py` contributes **3 of 14** hotspots (`data_for_file:134`, `write_html_page:467`,
     `write_region_index_pages:584`) — the most complex report backend by a wide margin, and also
     the one with the most per-backend concerns.
   - `config.py::CoverageConfig.from_file:296` — the INI/TOML dispatch point.
   - `cmdline.py::CoverageScript.command_line:793` — 128 lines but nesting 2; flat dispatch,
     briefing FP class 8. De-prioritise.

---

## Appendix: metrics used

**Fan-in (top 10):** `types.py` 29 · `exceptions.py` 23 · `misc.py` 22 · `plugin.py` 15 ·
`__init__.py` 14 · `env.py` 13 · `files.py` 10 · `debug.py` 9 · `results.py` 9 · `data.py` 7 /
`report_core.py` 7.

**Fan-out (top 10):** `control.py` 27 · `html.py` 11 · `cmdline.py` 10 · `core.py` 9 ·
`inorout.py` 9 · `python.py` 9 · `collector.py` 8 · `parser.py` 8 · `sysmon.py` 8 ·
`annotate.py` / `report.py` / `report_core.py` / `sqldata.py` / `xmlreport.py` 7.

**Zero internal imports (pure leaves):** `env.py`, `exceptions.py`, `numbits.py`, `templite.py`,
`version.py`. **Zero internal dependents:** `__main__.py`, `pth_file.py` (both expected).

**External dependencies (entire package):** `__pypy__`, `eventlet`, `gevent`, `greenlet` — all four
imported conditionally inside `collector.py:127-141`. No third-party runtime dependency.

**Re-exports:** one — `coverage/__init__.py`, no `__all__`, re-exports from `version`, `control`,
`data`, `exceptions`, `plugin`; uses the `X as X` idiom (`:19-34`) with the mypy rationale
documented at `:14-17`.
