# type-design-analyzer — coverage.py @ `6b3259ab`

**Target:** `/home/danzin/projects/coveragepy/coverage` (44 files, 16,426 lines) at `6b3259abb64a3cb80b4800f58fe1c71b24970110`.

**Did I edit the tree?** **No.** The target tree is untouched — verified by `git status --porcelain` (only the five pre-existing untracked files) and by `grep -rn "builtins.EV" coverage/` returning nothing. All work was done on `git archive HEAD` copies in `/tmp`.

> **Contamination notice (affects other agents, not this report).** My first scratch copy at
> `/tmp/covrepro` was **modified by a concurrently-running agent at 06:18:28 today**, which inserted
> two `builtins.EV = getattr(builtins,"EV",[]) + [...]` instrumentation lines into
> `/tmp/covrepro/coverage/pytracer.py` (after `sys.settrace(None)` at ~line 170, and at the top of
> `_trace()` at ~line 187). Those lines are **not in `HEAD`** — `git show HEAD:coverage/pytracer.py`
> and `git log -S "builtins.EV"` both come back empty. I detected this via a `mypy` run that
> reported two `Module has no attribute "EV"` errors, then confirmed with
> `diff -rq` against a pristine archive: **`pytracer.py` was the only file that differed.**
> I rebaselined onto a fresh archive (`/tmp/tda_probe_9911`) and re-verified every `pytracer.py`
> citation in this report against the pristine copy. **If another agent reports left-in debug
> instrumentation in `pytracer.py`, that finding is an artifact of its own scratch tree.**

---

## Type System Overview

coverage.py is at the top of the Python typing maturity curve: **99.3% annotation coverage (693/698 functions), a `py.typed` marker shipped to users, and a clean `mypy` run under a hand-assembled near-strict config.** I re-ran `mypy` on a pristine archive and reproduced `Success: no issues found in 45 source files`. There is no annotation work worth recommending here.

What the coverage number does not tell you is how much those annotations actually *check*. The project's domain is built almost entirely from `str` and `int`, and its type aliases (`TLineNo = int`, `TOffset = int`) are transparent — to `mypy` they are the identical type. **I wrote a ten-case probe exercising the type-design gaps below and ran it through the project's own mypy config. All ten passed clean.** That is the finding: the type system is comprehensive in *coverage* and largely inert in *discrimination*, and several already-catalogued FIX-severity defects sit exactly where a real type would have stopped them.

### Coverage statistics (from `count_types.json` / `check_typing.json`)

| Metric | Value |
|---|---|
| Functions fully annotated | 693 / 698 (99.3%) |
| Public functions fully annotated | 577 / 581 (99.3%) |
| Unannotated public functions | 4 — all `__init__`/`__exit__`, all **ACCEPTABLE** |
| `Any` usages | 40 |
| `# type: ignore` comments | 47 (`warn_unused_ignores = true` is set and mypy is clean ⇒ **0 stale**) |
| Containers | 13 `dataclass`, 10 `Protocol`, 1 `ABC`, **0 `TypedDict`, 0 `NamedTuple`, 0 `Enum`** |
| mypy | 1.20.2 with project config, `returncode 0`, 0 defects, strict pass ran |

**`strict_optional` verification (Part A.4):** confirmed **ON**. It defaults to `True` in every mypy since 0.600, `pyproject.toml [tool.mypy]` does not disable it, and it additionally sets `no_implicit_optional = true`. (Note: the `strict = true` at `pyproject.toml:125` is in `[tool.pytest.ini_options]`, **not** `[tool.mypy]` — mypy runs a hand-picked flag set, missing `strict`'s `no_implicit_reexport`, `strict_equality`, and `extra_checks`.) The Optional-return class is therefore genuinely checked; the only escapes are where an Optional flows into `Any` (see N9).

---

## The probe — ten gaps, zero mypy errors

Written against a pristine archive, checked with the project's own `pyproject.toml`:

```
$ mypy probe.py
Success: no issues found in 1 source file
```

| # | What the probe does | Why mypy is silent |
|---|---|---|
| P1 | passes a `TOffset` to a `TLineNo` parameter | both are `int` |
| P2 | passes a `TLineNo` to a `TOffset` parameter | both are `int` |
| P3 | `BranchArcResolver.line_at(lineno)` — a line number into an **offset**-keyed map | both are `int` |
| P4 | builds an arc `(end, start)` instead of `(start, end)` | `tuple[int, int]` either way |
| P5 | `fr.arc_description(end, start)` — two adjacent `TLineNo` args swapped | identical types |
| P6 | `Numbers(0,1,2,3,4,5,6,7)` — eight positional ints, any transposition | identical types |
| P7 | `cov.clear_exclude(which="partial_branches")` | `which: str` |
| P8 | `t.warn = 3`, `t.trace_arcs = "yes"`, `d.canonical_filename = 12` on the C tracer | stub declares them `Any` |
| P9 | a plugin returning `"py"` from `file_reporter()` | declared `FileReporter \| str` |
| P10 | `bytes_to_lines(code)[17]` — subscripting an offset-keyed dict with a line number | both are `int` |

The project already owns both fixes in its own vocabulary — `NewType` at `coverage/sysmon.py:59` and `Literal` at `coverage/data.py:117` — which is what makes these gaps findings rather than style preferences.

---

## Part A — Type design

### Catalogued (confirmed still present; type-design root only, not re-litigated)

**C1 — The path domain is one undifferentiated `str`. Root of CRF-COVPY-0014 / -0015 / -0035.**
`coverage/files.py` defines seven mutually-incompatible `str -> str` transforms — `relative_filename` (:52), `canonical_filename` (:65), `flat_rootname` (:90, which returns something that is *not a path at all*), `abs_file` (:156), `python_reported_file` (:190), `PathAliases.map` (:484), plus `zip_location` (:161) returning an unnamed `tuple[str, str]`. Every one is substitutable for every other at every call site.

The sharp edge is `coverage/control.py:304` / `:391`:

```python
self._file_mapper: Callable[[str], str] = abs_file    # :304
...
if self.config.relative_files:
    self._file_mapper = relative_filename             # :391
```

A single config flag swaps the *meaning* of every data-file key in the process, and the type is `Callable[[str], str]` in both worlds. `TFileDisposition` (`types.py:56-65`) then carries `original_filename`, `canonical_filename` and `source_filename` as three `str` fields with no way to tell them apart. This is why symlink normalization can disagree between `python.py:155-161` and `inorout.py:401` without any checker noticing.

*Fix:* `NewType("AbsPath", str)` / `NewType("RelPath", str)` / `NewType("FlatName", str)`. `NewType` is zero-cost at runtime and already used at `sysmon.py:59`. `_file_mapper` becomes `Callable[[str], AbsPath] | Callable[[str], RelPath]`, which forces the two worlds apart at the type level.

**C2 — `TConfigParser` is a bare union, and `getattr` string dispatch escapes it. Root of CRF-COVPY-0028 / -0029.**
`coverage/config.py:146` declares `TConfigParser = HandyConfigParser | TomlConfigParser` — a union of two concrete classes, not a `Protocol`. A union does protect *direct* attribute access (mypy requires the member on both arms), and I verified the seven directly-called methods (`read`, `has_option`, `has_section`, `options`, `real_section`, `get_section`, `getlist`) exist on both.

The hole is `coverage/config.py:485`:

```python
method = getattr(cp, f"get{type_}")
setattr(self, attr, method(section, option))
```

`type_` ranges over `{boolean, file, float, int, list, regexlist}` (from `CONFIG_FILE_OPTIONS`). Five of those six getters — `getboolean`, `getfile`, `getfloat`, `getint`, `getregexlist` — are reached **only** through this string, so nothing verifies that both backends implement them. `HandyConfigParser` inherits `getboolean`/`getint`/`getfloat` from `configparser.ConfigParser`; `TomlConfigParser` hand-writes them at `tomlconfig.py:180/204/208`. Add a `"path"` row to `CONFIG_FILE_OPTIONS` and implement `getpath` on one backend and you get a runtime `AttributeError` on one config format only, with a clean mypy run. That is the mechanism behind both catalogued TOML/INI divergences.

*Fix:* the guarded twin is two files away — `types.py` already defines `TConfigurable` and `TPluginConfig` as `Protocol`s. Declare `TConfigParser` as a `Protocol` with the six getters and let mypy verify conformance of both backends.

**C3 — CRF-COVPY-0018 confirmed still live.** `coverage/html.py:42` still reads `from coverage.plugins import FileReporter` under `TYPE_CHECKING`; `coverage/plugins.py` does not exist (the module is `plugin.py`). Verified by direct `ls`.

**C4 — CRF-COVPY-0020 confirmed still live.** `coverage/report_core.py:110` still calls `fr.should_be_python()` with `# type: ignore[attr-defined]` on a base-typed `FileReporter`.

### Novel findings

---

#### N1 — `Coverage.exclude()` / `clear_exclude()` / `get_exclude_list()` take `which: str`, and a wrong value silently builds a phantom exclusion list — **FIX**

`coverage/control.py:803-848`. Three public, `py.typed`-shipped methods dispatch on a bare string:

```python
def clear_exclude(self, which: str = "exclude") -> None:
    setattr(self.config, f"{which}_list", [])          # :806
def exclude(self, regex: str, which: str = "exclude") -> None:
    excl_list = getattr(self.config, f"{which}_list")  # :825
def get_exclude_list(self, which: str = "exclude") -> list[str]:
    return cast(list[str], getattr(self.config, f"{which}_list"))  # :848
```

The only legal values are `"exclude"`, `"partial"`, `"partial_always"` (`config.py:221/229/230`). Nothing — type or runtime — enforces that. Two things make a wrong value *likely* rather than hypothetical: the config-file option is spelled `partial_branches` (`config.py:438`) while the attribute is `partial_list`, so `which="partial_branches"` is the natural guess; and the `exclude()` docstring (`control.py:812-816`) documents only `"exclude"` and `"partial"`, never mentioning the real third value `"partial_always"`.

**Reproduced** on a pristine archive:

```
partial_list before:  ['#\s*(pragma|PRAGMA)[:\s]?\s*(no|NO)\s*(branch|BRANCH)'] ...
cov.clear_exclude(which="partial_branches")
partial_list after:   ['#\s*(pragma|PRAGMA)[:\s]?\s*(no|NO)\s*(branch|BRANCH)'] ... UNCHANGED
config.partial_branches_list = []            <- silently created
cov.exclude("zzz", which="partial_branches") -> no error
cov.get_exclude_list(which="partial_branches") -> ['zzz']
```

The API gives **fully consistent, entirely fictional feedback**: you clear the list, you add a regex, you read it back and see your regex — and coverage.py never consults that list for anything. Coverage output is silently wrong and the user has positive confirmation that it should be right.

Call order changes the failure mode completely. With `exclude()` *first* on a fresh object (no prior `clear_exclude`), the same argument raises `AttributeError: 'CoverageConfig' object has no attribute 'partial_branches_list'` — an internal-looking crash out of a public API. Same wrong input, two unrelated outcomes.

*Fix:* `which: Literal["exclude", "partial", "partial_always"]` on all three signatures (the project already uses `Literal` at `data.py:117`), plus a runtime `if which not in _EXCLUDE_KINDS: raise ConfigError(...)` for untyped callers, and add `"partial_always"` to the `exclude()` docstring.

---

#### N2 — `coverage/tracer.pyi` re-declares every Protocol member as `Any`, disabling type checking for the default tracer — **CONSIDER**

`coverage/tracer.pyi:10-45` is the stub for the C extension:

```python
class CFileDisposition(TFileDisposition):
    canonical_filename: Any
    file_tracer: Any
    original_filename: Any
    reason: Any
    source_filename: Any
    trace: Any
    has_dynamic_filename: Any

class CTracer(Tracer):
    data: TTraceData
    should_trace: Any
    should_trace_cache: Any
    switch_context: Any
    trace_arcs: Any
    warn: Any
    check_include: Any      # not in the Tracer Protocol at all
    concur_id_func: Any
    disable_plugin: Any
    file_tracers: Any
```

Both classes **subclass the Protocol that already declares these members precisely** (`types.py:56-65` gives `canonical_filename: str`, `trace: bool`, `reason: str`, `source_filename: str | None`; `types.py:86-97` gives `trace_arcs: bool`, `warn: TWarnFn`, `should_trace: TShouldTraceFn`, `should_trace_cache: Mapping[str, TFileDisposition | None]`). The stub then **shadows every one with `Any`**, discarding the inherited types.

This is not the legitimate "Any at a C boundary" case (FP class 10), because the precise types exist eleven lines away in the same package and are already inherited — deleting the redeclarations is the entire fix. The consequence is that `CTracer` is the *default* core on every non-3.14 CPython, and all Python-side configuration of it (`collector.py`) type-checks against nothing. Probe P8 assigns `t.warn = 3`, `t.trace_arcs = "yes"` and `d.canonical_filename = 12` with no mypy complaint. Note that CRF-COVPY-0003 is precisely a defect about `CTracer`'s `warn` member.

Two smaller drifts in the same file: it imports `Dict` from `typing` (deprecated form, unique in this 3.10+ codebase — every other module uses `dict`), and declares `get_stats(self) -> Dict[str, int]` where the Protocol says `dict[str, int] | None`.

*Fix:* delete the `Any` redeclarations and let the Protocol inheritance supply the types; declare the four extra attributes (`check_include`, `concur_id_func`, `disable_plugin`, `file_tracers`) with real types or add them to the `Tracer` Protocol.

---

#### N3 — `Numbers.__add__` is the one all-positional construction of an eight-`int` dataclass — **CONSIDER**

`coverage/results.py:384-394`:

```python
def __add__(self, other: Numbers) -> Numbers:
    return Numbers(
        self.precision,
        self.n_files + other.n_files,
        self.n_statements + other.n_statements,
        self.n_excluded + other.n_excluded,
        self.n_missing + other.n_missing,
        self.n_branches + other.n_branches,
        self.n_partial_branches + other.n_partial_branches,
        self.n_missing_branches + other.n_missing_branches,
    )
```

`Numbers` (`results.py:298-307`) is a plain `@dataclass` with eight same-typed `int` fields. Inserting, removing, or reordering any field leaves this call compiling and silently shifts every subsequent argument by one — `n_statements` receives the excluded count, and so on. Every reporter accumulates through this operator (`report.py:296`, `html.py:449`, `jsonreport.py:115`, `lcovreport.py:188`), so a shift corrupts every total in every format while all the numbers stay plausible-looking.

**Guarded twin, 280 lines up in the same file:** `results.py:105-114` constructs `Numbers` with all eight arguments as keywords. So do `html.py:349` and `report.py:47`. `__add__` is the sole positional site and the only one that must stay in sync with the field order.

*Fix:* keywords at `results.py:386-394` — a mechanical change that makes the whole class of error impossible. `@dataclass(frozen=True)` would be the stronger version (`Numbers` is an accumulating value object and `__radd__` at `:396` already returns `self` by aliasing); the project's own `ArcStart` at `parser.py:466` is `@dataclass(frozen=True, order=True)`, so the pattern is established.

---

#### N4 — `TTraceFileData` claims three shapes but expresses two, and its discriminator lives on a different object — **CONSIDER**

`coverage/types.py:68-78`. The comment documents three shapes (line numbers / arcs / *packed* arcs, two line numbers bit-packed into one int) and the alias reads:

```python
TTraceFileData = set[TLineNo] | set[TArc] | set[int]
```

Since `TLineNo = int` (`types.py:48`), **`set[TLineNo]` and `set[int]` are the identical type**. The union has three written members and two distinct ones; the "lines" case and the "packed arcs" case are indistinguishable, and they are the two that must never be confused — one holds line numbers, the other holds packed `(from, to)` pairs.

The discriminator is a boolean on a *different* object, `Core.packed_arcs` (`core.py:54`), which forces manual `cast()` at every consumer: `collector.py:467`, `:483`, `:489`, and `pytracer.py:266/268/299`. `pytracer.py:31-36` even carries a comment about having to hoist `set_TLineNo`/`set_TArc` to module level to make the casts work on PyPy.

Related, at `core.py:113-133`: `tracer_class`, `file_disposition_class`, `supports_plugins`, `packed_arcs` and `systrace` are five independent attributes set in three mutually exclusive branches. Nothing in the types prevents `tracer_class=SysMonitor` with `packed_arcs=True`, which would reinterpret every measured set.

*Fix:* `NewType("PackedArc", int)` makes `set[PackedArc]` a genuinely distinct third member and turns every `cast()` site into a checked one. Bundling the five `Core` attributes into one frozen per-core dataclass makes the illegal combinations unrepresentable.

---

#### N5 — `TArcFragments` is an anonymous pair of `str | None`, consumed by magic index — **CONSIDER**

`coverage/parser.py:524`:

```python
TArcFragments = dict[TArc, list[tuple[Optional[str], Optional[str]]]]
```

Produced at `parser.py:815` as `(missing_cause_msg, action_msg)`; consumed positionally at `parser.py:439` (`for missing_cause_msg, action_msg in fragment_pairs`) and — worse — at `parser.py:457`:

```python
action_msg = self._finish_action_msg(fragment_pairs[0][1], end)
```

Both members are `str | None`. Swapping them at the producer, or writing `[0][0]` instead of `[0][1]`, type-checks perfectly and produces a plausible-but-wrong English sentence in every report ("line 17 didn't the condition on line 17 was never true").

**Guarded twin, 60 lines below in the same file:** `ArcStart` (`parser.py:466-497`) is `@dataclass(frozen=True, order=True)` with named `lineno` and `cause` fields, doing the same job — annotating an arc — correctly. The project knows the pattern; this one alias predates it.

*Fix:* a `NamedTuple` (or frozen dataclass) `ArcFragment(missing_cause_msg: str | None, action_msg: str | None)`. `fragment_pairs[0].action_msg` reads correctly and cannot be transposed.

---

#### N6 — `CoveragePlugin.file_reporter()` returns `FileReporter | str` where the source comment says it shouldn't — **CONSIDER**

`coverage/plugin.py:174-189`:

```python
def file_reporter(self, filename: str) -> FileReporter | str:  # str should be Literal["python"]
```

The author has documented the defect in the signature itself. `"python"` is the only legal string; the consumer at `control.py:1049` tests `if file_reporter == "python":` and otherwise falls through to `assert isinstance(file_reporter, FileReporter)` at `:1052`. A third-party plugin returning `"py"` or `"Python"` type-checks fine at its own definition site (probe P9), then trips an `AssertionError` with no context — or, under `python -O` where asserts are stripped, lets a bare `str` flow onward as a `FileReporter`.

Also at `control.py:1042`: `if file_reporter is None: raise PluginError(...)` guards against a value the declared return type already excludes. It is not flagged by `warn_unreachable` only because the declared union is loose.

*Fix:* `-> FileReporter | Literal["python"]`, exactly as the comment says. This is a `py.typed` public plugin API, so the annotation propagates to every typed plugin author.

---

#### N7 — `TLineNo` is really a tagged union (line number *or* sign-encoded exit sentinel) with the tag encoded in the sign bit — **CONSIDER**

Negative line numbers mean "entered/exited a code object". They are minted at `parser.py:781`, `:784`, `:797`, `pytracer.py:299`, `sysmon.py:412`, and `bytecode.py:205`. Consumers must remember the encoding: `parser.py:271-276` branches on the sign and performs a double negation to reach a positively-keyed map —

```python
if lineno < 0:
    first = -self.multiline_map.get(-lineno, -lineno)
else:
    first = self.multiline_map.get(lineno, lineno)
```

— which is the *guarded twin*. `TLineNo = int` communicates none of this: no consumer is obliged to handle the negative case, and nothing validates that an arc's members are ordered or that a "line number" reaching a report renderer is a real line.

*Fix:* at minimum, document the sentinel convention on `types.py:47-53`, which currently says only "Line numbers are pervasive enough that they deserve their own type." The stronger form is a `NewType` for the exit sentinel so the union is visible in signatures.

---

#### N8 — `_file_id()`'s Optional return is unchecked at four call sites and checked at a fifth — **ACCEPTABLE / CONSIDER**

`coverage/sqldata.py:462` declares `_file_id(self, filename: str, add: bool = False) -> int | None`. The Optional is real only when `add=False`; with `add=True` the body always inserts and populates `_file_map`, so the result cannot be `None`. The four `add=True` callers (`:557`, `:599`, `:646`, `:682`) correctly do not check — and `:705` (`add=False`) correctly does:

```python
file_id = self._file_id(filename, add=False)
if file_id is None:
    continue
```

No live bug. But mypy does not catch a *future* unchecked `add=False` caller either, because the value flows into `SqliteDb.execute(..., parameters: Iterable[Any])` (`sqlitedb.py:135`) where `int | None` is absorbed. This is the one place `strict_optional` is genuinely defeated in the codebase.

*Fix:* `@overload` on `add: Literal[True] -> int` / `add: Literal[False] = ... -> int | None`. That makes the guarantee the four callers already rely on visible to the checker, and puts a real error on any future unchecked `add=False` use.

---

### Container-choice assessment

The 13 dataclasses / 10 Protocols / 1 ABC are all reasonable choices for what they hold. Two observations:

- **Zero `NamedTuple`, zero `TypedDict`, zero `Enum` in 16k lines.** The absence is visible in exactly the places N3/N5 identify — anonymous tuples (`Numbers.ratio_statements -> tuple[int, int]` at `results.py:328`, splatted positionally into `_percent(*self.ratio_covered)` at `results.py:339`; `TArcFragments`; `zip_location -> tuple[str, str] | None`) and string-typed enumerations (`which`, `"python"`, the three core names at `core.py:118-133`).
- **`ArcStart` is the model.** `@dataclass(frozen=True, order=True)` with named fields is the right shape for a value object and is the argument for N3 and N5.
- **Part A.2 (bare dicts with implicit keys): essentially clean.** The one JSON-ish boundary, `IncrementalChecker` (`html.py:770-796`), reads `status.json` into real dataclasses via `IndexItem(**indexdict)` / `Numbers(**indexdict["nums"])` and is guarded by both a `STATUS_FORMAT` version and an exact `coverage.__version__` match (`html.py:764-767`), so a key-shape mismatch cannot be reached. `JsonObj = dict[str, Any]` (`jsonreport.py:26`) is the report *output* format — a genuine serialization boundary, correctly `Any`. **Not a finding.**

---

## Part B — Dead code, second look

The scanner reported 0 unused imports, 0 unreferenced symbols, 0 orphan files, 1 commented-out block over 44/44 files. **That result is essentially correct**, with one real exception it structurally could not see. Category by category:

### Verified empty

- **`sys.version_info` branches below the supported floor.** `setup.py:225` sets `python_requires=">=3.10"`. There are exactly **three** `sys.version_info` uses in `coverage/`: `phystokens.py:104` (`>= (3, 12)`), `phystokens.py:106` (`>= (3, 15)`), and `env.py:35` (the `PYVERSION` definition). All are at or above the floor. **No dead version branch exists.** The codebase deliberately funnels version tests through `env.PYVERSION` / `env.PYBEHAVIOR` (documented at `env.py:33-34`), and every `PYBEHAVIOR` flag compares against 3.12+.
- **`__all__` re-exports.** `grep -rn "__all__" coverage/*.py` returns **nothing** — no module in the package defines `__all__`. There is no re-export surface that can be broken, so the whole category is vacuous here.
- **Entry points.** Both `console_scripts` targets from `setup.py:186-193` exist: `main` at `cmdline.py:1168` and `main_deprecated` at `cmdline.py:1200`.
- **Typo'd string-dispatched handlers.** `parser.py:828` and `:913` dispatch AST handlers by `getattr(self, f"_line__{node_name}")` / `f"_handle__{node_name}"`. I enumerated all sixteen defined handlers (`_line__Assign/Dict/List/Module/AsyncFunctionDef`, `_handle__Break/Continue/For/If/Match/Raise/Return/Try/While/With/AsyncFor/AsyncFunctionDef/AsyncWith/TryStar`) and verified every suffix against `ast` with `hasattr(ast, name)` — **all resolve to real node classes. No hook can never fire.** The `_code_object__*` family is not `getattr`-dispatched at all; it is called by explicit `isinstance` at `parser.py:738-743`.
- **The one commented-out block.** `cmdline.py:750-754` is **prose, not code** — an explanatory comment beginning `# entry_points={"console_scripts":...} on Windows makes files`. Stripping the `#` and running `ast.parse` raises `SyntaxError: invalid syntax`, the mechanical discriminator from FP class 39. **The scanner's single finding is a false positive.** Nothing to remove.

### Not dead, though a naive pass would say so

`env.MACOS`, `env.PYPYVERSION`, `env.GIL`, `env.FREE_THREADED` have **zero** references anywhere in the repository, including `tests/`. They are nonetheless live: `env.debug_info()` (`env.py:132-142`) enumerates `globals()` and `PYBEHAVIOR.__dict__`, and is called from `cmdline.py:1099` and `control.py:435` to produce `coverage debug pybehave`. Removing any of them removes diagnostic output. Recorded here so the next reviewer does not re-derive it.

### The one real finding the scanner could not see

#### N9 — `Core.tracer_kwargs` has been dead since commit `4b0fc857`, and it disables type checking of the tracer constructor — **CONSIDER**

`coverage/core.py:51` declares `tracer_kwargs: dict[str, Any]`, `core.py:113` assigns `self.tracer_kwargs = {}`, and `collector.py:251` consumes it:

```python
tracer = self.core.tracer_class(**self.core.tracer_kwargs)
```

**Nothing anywhere in the repository ever puts a key in it.** `grep -rn "tracer_kwargs" /tmp/tda_probe_9911` returns exactly those three lines and no others — no test, no doc, no plugin. Git history explains why: commit `4b0fc857` ("fix: find a usable sys.monitoring toolid instead of assuming COVERAGE_ID is available. #2187", 2026-06-08) deleted the sole writer, `self.tracer_kwargs["tool_id"] = 3 if metacov else 1`, and left the plumbing behind.

The static scanner cannot see this because the attribute *is* referenced — twice. It is dead by *value*, not by reference, which no name-reference analysis reaches.

There is a live type cost beyond the dead code. `Tracer.__init__` is declared `def __init__(self) -> None` in the Protocol (`types.py:99`), so the tracer constructor takes no arguments — but `**self.core.tracer_kwargs` is `dict[str, Any]`, so mypy accepts the splat unconditionally and verifies nothing about that call. Removing the attribute and calling `self.core.tracer_class()` restores checking of the one constructor that matters.

*Fix:* delete `core.py:51` and `core.py:113`; change `collector.py:251` to `tracer = self.core.tracer_class()`.

---

## Recommendations, in priority order

1. **`Literal` the `which` parameter** on `Coverage.exclude` / `clear_exclude` / `get_exclude_list` (`control.py:803-848`) and add a runtime guard. This is a shipped `py.typed` public API that currently accepts a typo and silently reports wrong coverage while confirming to the caller that it did the right thing. **(N1, FIX)**
2. **Delete the `Any` redeclarations in `coverage/tracer.pyi`.** They shadow precise Protocol types that are already inherited, and they blind the checker to the default tracer's entire configuration surface. Pure deletion. **(N2)**
3. **Make `Numbers.__add__` use keyword arguments** (`results.py:386-394`) — one-line-per-field mechanical change, matches the three sibling construction sites, and removes a whole class of silent field-shift corruption. **(N3)**
4. **Remove `Core.tracer_kwargs`** (`core.py:51`, `:113`, `collector.py:251`). Dead since `4b0fc857`, and its removal restores type checking of the tracer constructor. **(N9)**
5. **`NewType` the path domain** — `AbsPath` / `RelPath` / `FlatName` in `files.py` and `types.py`. This is the largest change here, but it is where three catalogued FIX-severity defects (CRF-COVPY-0014/-0015/-0035) share a root, and `NewType` costs nothing at runtime. **(C1)**
6. **Promote `TConfigParser` from a union to a `Protocol`** (`config.py:146`), so the five string-dispatched getters are conformance-checked across the INI and TOML backends. Root of CRF-COVPY-0028/-0029. **(C2)**
7. **Name the arc-fragment pair** (`parser.py:524`) and **apply the comment's own advice** to `file_reporter` (`plugin.py:177`). Both are small and both are already-identified by the code itself. **(N5, N6)**
8. **Do not spend effort on annotation coverage.** 99.3%, four unannotated `__init__`/`__exit__`, `warn_unused_ignores` on with 0 stale ignores among 47. There is nothing here.

### Policy note

The project runs mypy with a hand-assembled flag list rather than `strict = true` (`pyproject.toml:10-27`). It is missing `no_implicit_reexport`, `strict_equality` and `extra_checks`. `strict_equality` in particular would be worth enabling: it flags non-overlapping comparisons, which is the exact shape of `control.py:1049` (`if file_reporter == "python"`) once N6's `Literal` lands. **(POLICY)**
