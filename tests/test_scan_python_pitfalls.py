"""Tests for scan_python_pitfalls.py.

Each shape gets a true positive, its guarded twin (which must stay silent), and
an edge case. The guarded-twin assertions matter most: a scanner that fires on
the documented fix is worse than no scanner.
"""

import unittest

from helpers import TempProject, import_script

mod = import_script("scan_python_pitfalls")


def scan(source: str, **kw) -> list[dict]:
    """Scan a single module and return its findings."""
    with TempProject({"mod.py": source}) as root:
        return mod.analyze(str(root / "mod.py"), **kw)["findings"]


def shapes(source: str) -> list[str]:
    return [f["shape"] for f in scan(source)]


class TestMutableDefault(unittest.TestCase):
    def test_list_default_mutated(self):
        f = scan("def f(x, items=[]):\n    items.append(x)\n")
        self.assertEqual(f[0]["shape"], "mutable-default-argument")
        self.assertEqual(f[0]["confidence"], "high")

    def test_dict_and_set_defaults(self):
        self.assertIn(
            "mutable-default-argument", shapes("def f(a={}):\n    a['k']=1\n")
        )
        self.assertIn(
            "mutable-default-argument", shapes("def f(a=set()):\n    a.add(1)\n")
        )

    def test_evaluated_once_call(self):
        src = "import datetime\ndef f(now=datetime.datetime.now()):\n    return now\n"
        self.assertIn("mutable-default-argument", shapes(src))

    def test_readonly_default_downgraded(self):
        f = scan("def f(opts={}):\n    print(opts)\n")
        self.assertEqual(f[0]["confidence"], "medium")

    def test_returned_default_is_high(self):
        f = scan("def f(items=[]):\n    return items\n")
        self.assertEqual(f[0]["confidence"], "high")

    def test_keyword_only_default(self):
        self.assertIn(
            "mutable-default-argument", shapes("def f(*, x=[]):\n    x.append(1)\n")
        )

    def test_none_sentinel_is_silent(self):
        src = "def f(x, items=None):\n    items = [] if items is None else items\n    items.append(x)\n"
        self.assertNotIn("mutable-default-argument", shapes(src))

    def test_immutable_defaults_silent(self):
        src = "def f(a=1, b='s', c=(), d=None, e=frozenset()):\n    return a\n"
        self.assertNotIn("mutable-default-argument", shapes(src))


class TestLateBindingClosure(unittest.TestCase):
    def test_lambda_in_loop(self):
        src = "def f():\n    out = []\n    for i in range(3):\n        out.append(lambda: i)\n    return out\n"
        self.assertIn("late-binding-closure-in-loop", shapes(src))

    def test_nested_def_in_loop(self):
        src = "def f(names):\n    for n in names:\n        def go():\n            return n\n        register(go)\n"
        self.assertIn("late-binding-closure-in-loop", shapes(src))

    def test_default_arg_binding_is_silent(self):
        src = "def f():\n    return [lambda i=i: i for i in range(3)]\n"
        self.assertNotIn("late-binding-closure-in-loop", shapes(src))

    def test_closure_not_using_loop_var_is_silent(self):
        src = "def f(k):\n    out = []\n    for i in range(3):\n        out.append(lambda: k)\n    return out\n"
        self.assertNotIn("late-binding-closure-in-loop", shapes(src))


class TestExceptOrdering(unittest.TestCase):
    def test_broad_before_narrow(self):
        src = "def f():\n    try:\n        pass\n    except Exception:\n        pass\n    except ValueError:\n        pass\n"
        # The same fixture also legitimately triggers except-exception-too-broad,
        # so select by shape rather than by position.
        f = [x for x in scan(src) if x["shape"] == "except-clause-ordering-unreachable"]
        self.assertEqual(len(f), 1)
        self.assertEqual(f[0]["confidence"], "high")

    def test_oserror_before_filenotfound(self):
        src = "def f():\n    try:\n        pass\n    except OSError:\n        pass\n    except FileNotFoundError:\n        pass\n"
        self.assertIn("except-clause-ordering-unreachable", shapes(src))

    def test_correct_order_is_silent(self):
        src = "def f():\n    try:\n        pass\n    except ValueError:\n        pass\n    except Exception:\n        pass\n"
        self.assertNotIn("except-clause-ordering-unreachable", shapes(src))

    def test_unrelated_types_silent(self):
        src = "def f():\n    try:\n        pass\n    except ValueError:\n        pass\n    except KeyError:\n        pass\n"
        self.assertNotIn("except-clause-ordering-unreachable", shapes(src))

    def test_user_defined_exceptions_not_guessed(self):
        # Hierarchy is unknowable statically -- must not fabricate a finding.
        src = "def f():\n    try:\n        pass\n    except MyBase:\n        pass\n    except MySub:\n        pass\n"
        self.assertNotIn("except-clause-ordering-unreachable", shapes(src))


class TestReturnInFinally(unittest.TestCase):
    def test_return_in_finally(self):
        src = "def f():\n    try:\n        raise ValueError\n    finally:\n        return 1\n"
        self.assertIn("return-or-break-in-finally", shapes(src))

    def test_break_in_finally(self):
        src = "def f():\n    for _ in range(3):\n        try:\n            pass\n        finally:\n            break\n"
        self.assertIn("return-or-break-in-finally", shapes(src))

    def test_plain_finally_is_silent(self):
        src = "def f():\n    try:\n        return compute()\n    finally:\n        release()\n"
        self.assertNotIn("return-or-break-in-finally", shapes(src))

    def test_return_in_nested_def_is_silent(self):
        # The return belongs to the inner function, not to the finally.
        src = "def f():\n    try:\n        pass\n    finally:\n        def helper():\n            return 1\n        helper()\n"
        self.assertNotIn("return-or-break-in-finally", shapes(src))


class TestEqWithoutHash(unittest.TestCase):
    def test_eq_only(self):
        self.assertIn(
            "eq-without-hash",
            shapes("class C:\n    def __eq__(self, o):\n        return True\n"),
        )

    def test_eq_and_hash_silent(self):
        src = "class C:\n    def __eq__(self, o):\n        return True\n    def __hash__(self):\n        return 1\n"
        self.assertNotIn("eq-without-hash", shapes(src))

    def test_frozen_dataclass_silent(self):
        src = "from dataclasses import dataclass\n@dataclass(frozen=True)\nclass C:\n    x: int\n    def __eq__(self, o):\n        return True\n"
        self.assertNotIn("eq-without-hash", shapes(src))

    def test_explicit_hash_none_silent(self):
        src = "class C:\n    __hash__ = None\n    def __eq__(self, o):\n        return True\n"
        self.assertNotIn("eq-without-hash", shapes(src))


class TestMutationDuringIteration(unittest.TestCase):
    def test_del_during_dict_iteration(self):
        self.assertIn(
            "mutation-during-iteration",
            shapes("def f(d):\n    for k in d:\n        del d[k]\n"),
        )

    def test_remove_during_list_iteration(self):
        self.assertIn(
            "mutation-during-iteration",
            shapes("def f(lst):\n    for x in lst:\n        lst.remove(x)\n"),
        )

    def test_iterating_items_view(self):
        self.assertIn(
            "mutation-during-iteration",
            shapes("def f(d):\n    for k, v in d.items():\n        d.pop(k)\n"),
        )

    def test_snapshot_is_silent(self):
        self.assertNotIn(
            "mutation-during-iteration",
            shapes("def f(d):\n    for k in list(d):\n        del d[k]\n"),
        )

    def test_slice_copy_is_silent(self):
        self.assertNotIn(
            "mutation-during-iteration",
            shapes("def f(lst):\n    for x in lst[:]:\n        lst.remove(x)\n"),
        )

    def test_rewriting_existing_key_is_silent(self):
        # d[k] = v with k from the iteration rewrites an existing entry: the
        # size is unchanged, so CPython does not raise. Observed on idlelib,
        # where all four raw hits were this safe pattern.
        self.assertNotIn(
            "mutation-during-iteration",
            shapes("def f(d):\n    for k in d:\n        d[k] = transform(d[k])\n"),
        )

    def test_rewriting_via_items_is_silent(self):
        src = "def f(d):\n    for k, v in d.items():\n        d[k] = v + 1\n"
        self.assertNotIn("mutation-during-iteration", shapes(src))

    def test_inserting_a_new_key_is_flagged(self):
        # A different key can insert -> size change -> RuntimeError.
        self.assertIn(
            "mutation-during-iteration",
            shapes("def f(d):\n    for k in d:\n        d[k + '_x'] = 1\n"),
        )

    def test_list_index_assignment_is_silent(self):
        src = "def f(lst):\n    for i, x in enumerate(lst):\n        lst[i] = x * 2\n"
        self.assertNotIn("mutation-during-iteration", shapes(src))

    def test_mutating_a_different_container_silent(self):
        self.assertNotIn(
            "mutation-during-iteration",
            shapes("def f(a, b):\n    for x in a:\n        b.append(x)\n"),
        )


class TestFireAndForgetTask(unittest.TestCase):
    def test_bare_create_task(self):
        src = "import asyncio\nasync def f():\n    asyncio.create_task(go())\n"
        self.assertIn("asyncio-fire-and-forget-task", shapes(src))

    def test_retained_task_is_silent(self):
        src = "import asyncio\nasync def f(tasks):\n    t = asyncio.create_task(go())\n    tasks.add(t)\n"
        self.assertNotIn("asyncio-fire-and-forget-task", shapes(src))

    def test_awaited_is_silent(self):
        src = "import asyncio\nasync def f():\n    await asyncio.create_task(go())\n"
        self.assertNotIn("asyncio-fire-and-forget-task", shapes(src))


class TestBlockingInAsync(unittest.TestCase):
    def test_time_sleep(self):
        src = "import time\nasync def f():\n    time.sleep(1)\n"
        self.assertIn("blocking-call-in-async-function", shapes(src))

    def test_requests_get(self):
        src = "import requests\nasync def f():\n    requests.get('u')\n"
        self.assertIn("blocking-call-in-async-function", shapes(src))

    def test_asyncio_sleep_is_silent(self):
        src = "import asyncio\nasync def f():\n    await asyncio.sleep(1)\n"
        self.assertNotIn("blocking-call-in-async-function", shapes(src))

    def test_blocking_in_sync_function_is_silent(self):
        src = "import time\ndef f():\n    time.sleep(1)\n"
        self.assertNotIn("blocking-call-in-async-function", shapes(src))


class TestUnawaitedCoroutine(unittest.TestCase):
    def test_bare_call_to_local_coroutine(self):
        src = "async def work():\n    return 1\nasync def caller():\n    work()\n"
        self.assertIn("unawaited-coroutine", shapes(src))

    def test_awaited_is_silent(self):
        src = "async def work():\n    return 1\nasync def caller():\n    await work()\n"
        self.assertNotIn("unawaited-coroutine", shapes(src))

    def test_gathered_is_silent(self):
        src = "import asyncio\nasync def work():\n    return 1\nasync def caller():\n    await asyncio.gather(work(), work())\n"
        self.assertNotIn("unawaited-coroutine", shapes(src))

    def test_sync_function_call_is_silent(self):
        src = "def work():\n    return 1\nasync def caller():\n    work()\n"
        self.assertNotIn("unawaited-coroutine", shapes(src))


class TestLruCacheOnMethod(unittest.TestCase):
    def test_lru_cache_with_self(self):
        src = "import functools\nclass C:\n    @functools.lru_cache\n    def m(self, k):\n        return k\n"
        self.assertIn("lru-cache-on-method", shapes(src))

    def test_cached_property_is_silent(self):
        src = "import functools\nclass C:\n    @functools.cached_property\n    def m(self):\n        return 1\n"
        self.assertNotIn("lru-cache-on-method", shapes(src))

    def test_module_level_function_is_silent(self):
        src = "import functools\n@functools.lru_cache\ndef f(k):\n    return k\n"
        self.assertNotIn("lru-cache-on-method", shapes(src))

    def test_staticmethod_is_silent(self):
        src = "import functools\nclass C:\n    @staticmethod\n    @functools.lru_cache\n    def m(k):\n        return k\n"
        self.assertNotIn("lru-cache-on-method", shapes(src))


class TestClassLevelMutable(unittest.TestCase):
    def test_class_list(self):
        f = scan("class C:\n    items = []\n")
        self.assertEqual(f[0]["shape"], "class-level-mutable-attribute")

    def test_all_caps_unmutated_is_low(self):
        f = scan("class C:\n    DEFAULTS = {}\n")
        self.assertEqual(f[0]["confidence"], "low")

    def test_declarative_config_downgraded(self):
        # Never mutated in the module: the menu_specs/Meta pattern, seen
        # throughout idlelib. Real, but not a shared-state defect.
        f = scan("class C:\n    specs = [('a', 1), ('b', 2)]\n")
        self.assertEqual(f[0]["confidence"], "medium")

    def test_mutated_attribute_is_high(self):
        src = (
            "class C:\n    items = []\n"
            "    def add(self, x):\n        self.items.append(x)\n"
        )
        f = [x for x in scan(src) if x["shape"] == "class-level-mutable-attribute"]
        self.assertEqual(f[0]["confidence"], "high")

    def test_instance_attribute_is_silent(self):
        src = "class C:\n    def __init__(self):\n        self.items = []\n"
        self.assertNotIn("class-level-mutable-attribute", shapes(src))

    def test_dataclass_field_is_silent(self):
        src = "from dataclasses import dataclass, field\n@dataclass\nclass C:\n    items: list = field(default_factory=list)\n"
        self.assertNotIn("class-level-mutable-attribute", shapes(src))

    def test_immutable_class_attribute_is_silent(self):
        self.assertNotIn(
            "class-level-mutable-attribute", shapes("class C:\n    NAME = 'x'\n")
        )


class TestBareExcept(unittest.TestCase):
    def test_bare_except(self):
        f = scan("def f():\n    try:\n        pass\n    except:\n        pass\n")
        self.assertEqual(f[0]["shape"], "bare-except-swallows-control-flow")
        self.assertEqual(f[0]["confidence"], "high")

    def test_base_exception(self):
        src = "def f():\n    try:\n        pass\n    except BaseException:\n        pass\n"
        self.assertIn("bare-except-swallows-control-flow", shapes(src))

    def test_reraise_is_silent(self):
        src = "def f():\n    try:\n        pass\n    except BaseException:\n        raise\n"
        self.assertNotIn("bare-except-swallows-control-flow", shapes(src))

    def test_captured_for_caller_downgraded(self):
        # The thread/worker-body pattern: capture now, re-raise in the caller.
        src = "def f(errs):\n    try:\n        pass\n    except BaseException as e:\n        errs.append(e)\n"
        f = [x for x in scan(src) if x["shape"] == "bare-except-swallows-control-flow"]
        self.assertEqual(f[0]["confidence"], "medium")

    def test_earlier_systemexit_reraise_downgrades(self):
        # `except SystemExit: raise` then bare except -- the idlelib rpc.py idiom.
        src = (
            "def f():\n    try:\n        pass\n    except SystemExit:\n"
            "        raise\n    except:\n        log()\n"
        )
        f = [x for x in scan(src) if x["shape"] == "bare-except-swallows-control-flow"]
        self.assertEqual(f[0]["confidence"], "medium")
        self.assertIn("KeyboardInterrupt", f[0]["detail"])

    def test_all_control_flow_reraised_is_silent(self):
        src = (
            "def f():\n    try:\n        pass\n"
            "    except (SystemExit, KeyboardInterrupt, GeneratorExit):\n        raise\n"
            "    except:\n        log()\n"
        )
        self.assertNotIn("bare-except-swallows-control-flow", shapes(src))

    def test_except_exception_is_silent(self):
        src = "def f():\n    try:\n        pass\n    except Exception:\n        pass\n"
        self.assertNotIn("bare-except-swallows-control-flow", shapes(src))


class TestExceptionInDel(unittest.TestCase):
    def test_unguarded_del(self):
        src = "class C:\n    def __del__(self):\n        self.handle.close()\n"
        self.assertIn("exception-in-del-or-finalizer", shapes(src))

    def test_guarded_del_is_silent(self):
        src = "class C:\n    def __del__(self):\n        try:\n            self.handle.close()\n        except Exception:\n            pass\n"
        self.assertNotIn("exception-in-del-or-finalizer", shapes(src))

    def test_trivial_del_is_silent(self):
        src = "class C:\n    def __del__(self):\n        self.closed = True\n"
        self.assertNotIn("exception-in-del-or-finalizer", shapes(src))


class TestIsLiteral(unittest.TestCase):
    def test_is_int_literal(self):
        self.assertIn(
            "is-comparison-with-literal", shapes("def f(x):\n    return x is 256\n")
        )

    def test_is_str_literal(self):
        self.assertIn(
            "is-comparison-with-literal", shapes("def f(x):\n    return x is 'name'\n")
        )

    def test_is_none_is_silent(self):
        self.assertNotIn(
            "is-comparison-with-literal", shapes("def f(x):\n    return x is None\n")
        )

    def test_is_bool_is_silent(self):
        src = "def f(x):\n    return x is True or x is False\n"
        self.assertNotIn("is-comparison-with-literal", shapes(src))

    def test_equality_is_silent(self):
        self.assertNotIn(
            "is-comparison-with-literal", shapes("def f(x):\n    return x == 256\n")
        )


class TestEnvelopeAndOptions(unittest.TestCase):
    def test_envelope_keys(self):
        with TempProject({"m.py": "x = 1\n"}) as root:
            result = mod.analyze(str(root))
        for key in (
            "project_root",
            "scan_root",
            "files_total",
            "files_analyzed",
            "files_capped",
        ):
            self.assertIn(key, result)
        for key in (
            "by_shape",
            "by_severity",
            "by_confidence",
            "by_directory",
            "checks_run",
        ):
            self.assertIn(key, result["summary"])

    def test_file_target_scans_only_that_file(self):
        # Pointing at one file must not silently scan the whole project.
        with TempProject(
            {
                "a.py": "def f(x=[]):\n    x.append(1)\n",
                "b.py": "def g(y=[]):\n    y.append(1)\n",
            }
        ) as root:
            result = mod.analyze(str(root / "a.py"))
        self.assertEqual(result["files_analyzed"], 1)
        self.assertEqual(result["summary"]["total_findings"], 1)

    def test_check_filter(self):
        src = "def f(x=[]):\n    x.append(1)\ndef g():\n    return 1 is 2\n"
        with TempProject({"m.py": src}) as root:
            result = mod.analyze(str(root), checks=["is-comparison-with-literal"])
        found = {f["shape"] for f in result["findings"]}
        self.assertEqual(found, {"is-comparison-with-literal"})

    def test_exclude_pattern(self):
        files = {
            "src/a.py": "def f(x=[]):\n    x.append(1)\n",
            "generated/b.py": "def g(y=[]):\n    y.append(1)\n",
        }
        with TempProject(files) as root:
            result = mod.analyze(str(root), exclude=["generated/"])
        self.assertEqual(result["summary"]["total_findings"], 1)
        self.assertIn("src", result["summary"]["by_directory"])

    def test_findings_are_sorted(self):
        with TempProject(
            {"m.py": "def f(x=[]):\n    x.append(1)\ndef g(y=[]):\n    y.append(1)\n"}
        ) as root:
            findings = mod.analyze(str(root))["findings"]
        keys = [(f["file"], f["line"], f["shape"]) for f in findings]
        self.assertEqual(keys, sorted(keys))

    def test_syntax_error_file_does_not_abort(self):
        files = {
            "bad.py": "def broken( :\n",
            "good.py": "def f(x=[]):\n    x.append(1)\n",
        }
        with TempProject(files) as root:
            result = mod.analyze(str(root))
        self.assertEqual(result["summary"]["total_findings"], 1)

    def test_every_check_maps_to_a_catalogued_shape(self):
        catalog = import_script("build_informed_briefing")
        ids = {s["id"] for s in catalog._load_shapes()}
        self.assertEqual(set(mod._CHECKS) - ids, set())

    def test_every_finding_carries_required_fields(self):
        findings = scan("def f(x=[]):\n    x.append(1)\n")
        for key in ("shape", "severity", "confidence", "file", "line", "message"):
            self.assertIn(key, findings[0])


class TestExceptExceptionTooBroad(unittest.TestCase):
    """The gist's #1 family: ~50% of 40 confirmed CPython stdlib findings."""

    def test_narrow_body_swallowed_is_high(self):
        src = (
            "def f(o):\n    try:\n        x = o.a.b.c\n"
            "    except Exception:\n        x = None\n    return x\n"
        )
        f = [x for x in scan(src) if x["shape"] == "except-exception-too-broad"]
        self.assertEqual(f[0]["confidence"], "high")

    def test_narrow_body_with_pass_is_high(self):
        src = "def f(o):\n    try:\n        o.flush()\n    except Exception:\n        pass\n"
        f = [x for x in scan(src) if x["shape"] == "except-exception-too-broad"]
        self.assertEqual(f[0]["confidence"], "high")

    def test_base_exception_also_flagged(self):
        src = "def f(o):\n    try:\n        o.flush()\n    except BaseException:\n        pass\n"
        self.assertIn("except-exception-too-broad", shapes(src))

    def test_loud_logging_downgrades(self):
        src = (
            "import logging\nlog = logging.getLogger(__name__)\n"
            "def f(o):\n    try:\n        o.flush()\n"
            "    except Exception:\n        log.exception('failed')\n"
        )
        f = [x for x in scan(src) if x["shape"] == "except-exception-too-broad"]
        self.assertEqual(f[0]["confidence"], "medium")

    def test_large_body_boundary_is_low(self):
        src = (
            "def f(p):\n    try:\n        p.setup()\n        p.configure()\n"
            "        p.start()\n        p.verify()\n    except Exception:\n        pass\n"
        )
        f = [x for x in scan(src) if x["shape"] == "except-exception-too-broad"]
        self.assertEqual(f[0]["confidence"], "low")

    def test_narrow_exception_type_is_silent(self):
        src = (
            "def f(o):\n    try:\n        return o.a.b\n"
            "    except AttributeError:\n        return None\n"
        )
        self.assertNotIn("except-exception-too-broad", shapes(src))

    def test_reraising_handler_is_silent(self):
        src = "def f(o):\n    try:\n        o.flush()\n    except Exception:\n        raise\n"
        self.assertNotIn("except-exception-too-broad", shapes(src))


class TestCleanupOnlyOnSuccess(unittest.TestCase):
    def test_close_last_in_try_is_flagged(self):
        src = (
            "def f(c):\n    try:\n        c.send(1)\n        c.check()\n"
            "        c.close()\n    except OSError:\n        pass\n"
        )
        self.assertIn("cleanup-only-on-success-path", shapes(src))

    def test_close_in_finally_is_silent(self):
        src = (
            "def f(c):\n    try:\n        c.send(1)\n    finally:\n        c.close()\n"
        )
        self.assertNotIn("cleanup-only-on-success-path", shapes(src))

    def test_handler_also_closes_is_silent(self):
        src = (
            "def f(c):\n    try:\n        c.send(1)\n        c.close()\n"
            "    except OSError:\n        c.close()\n"
        )
        self.assertNotIn("cleanup-only-on-success-path", shapes(src))

    def test_non_release_call_is_silent(self):
        src = (
            "def f(c):\n    try:\n        c.send(1)\n        c.flush()\n"
            "    except OSError:\n        pass\n"
        )
        self.assertNotIn("cleanup-only-on-success-path", shapes(src))


class TestErrorReportedBelowWarning(unittest.TestCase):
    def test_debug_only_is_flagged(self):
        src = (
            "import logging\nlog = logging.getLogger(__name__)\n"
            "def f(o):\n    try:\n        o.decref()\n"
            "    except Exception:\n        log.debug('failed')\n"
        )
        self.assertIn("error-reported-below-warning", shapes(src))

    def test_warning_is_silent(self):
        src = (
            "import logging\nlog = logging.getLogger(__name__)\n"
            "def f(o):\n    try:\n        o.decref()\n"
            "    except Exception:\n        log.warning('failed')\n"
        )
        self.assertNotIn("error-reported-below-warning", shapes(src))

    def test_reraise_is_silent(self):
        src = (
            "import logging\nlog = logging.getLogger(__name__)\n"
            "def f(o):\n    try:\n        o.decref()\n"
            "    except Exception:\n        log.debug('x')\n        raise\n"
        )
        self.assertNotIn("error-reported-below-warning", shapes(src))


class TestExceptInLoopWithoutExit(unittest.TestCase):
    def test_swallow_in_while_true_is_flagged(self):
        src = (
            "def f(p):\n    while True:\n        try:\n            return listdir(p)\n"
            "        except OSError:\n            pass\n"
        )
        self.assertIn("except-in-loop-without-exit", shapes(src))

    def test_break_in_handler_is_silent(self):
        src = (
            "def f(p):\n    while True:\n        try:\n            return listdir(p)\n"
            "        except OSError:\n            break\n"
        )
        self.assertNotIn("except-in-loop-without-exit", shapes(src))

    def test_raise_in_handler_is_silent(self):
        src = (
            "def f(p):\n    while True:\n        try:\n            return listdir(p)\n"
            "        except OSError:\n            raise\n"
        )
        self.assertNotIn("except-in-loop-without-exit", shapes(src))

    def test_queue_empty_poll_loop_is_silent(self):
        # idlelib rpc.py/run.py: "nothing queued right now" is the design.
        src = (
            "import queue\ndef f(q):\n    while True:\n        try:\n"
            "            msg = q.get(0)\n        except queue.Empty:\n            pass\n"
            "        do_other_work()\n"
        )
        self.assertNotIn("except-in-loop-without-exit", shapes(src))

    def test_timeout_poll_loop_is_silent(self):
        src = (
            "def f(s):\n    while True:\n        try:\n            return s.recv()\n"
            "        except TimeoutError:\n            pass\n"
        )
        self.assertNotIn("except-in-loop-without-exit", shapes(src))

    def test_oserror_scan_loop_still_flagged(self):
        # The gist's genuine instance: a real failure, not a poll signal.
        src = (
            "def f(p):\n    while True:\n        try:\n            return listdir(p)\n"
            "        except OSError:\n            pass\n"
        )
        self.assertIn("except-in-loop-without-exit", shapes(src))

    def test_bounded_loop_is_silent(self):
        src = (
            "def f(p):\n    for _ in range(3):\n        try:\n            return listdir(p)\n"
            "        except OSError:\n            pass\n"
        )
        self.assertNotIn("except-in-loop-without-exit", shapes(src))


class TestRaiseWithoutFrom(unittest.TestCase):
    def test_missing_from_is_flagged(self):
        src = (
            "def f(t):\n    try:\n        return int(t)\n"
            "    except ValueError as err:\n        raise TypeError('bad')\n"
        )
        self.assertIn("raise-without-from-in-except", shapes(src))

    def test_from_err_is_silent(self):
        src = (
            "def f(t):\n    try:\n        return int(t)\n"
            "    except ValueError as err:\n        raise TypeError('bad') from err\n"
        )
        self.assertNotIn("raise-without-from-in-except", shapes(src))

    def test_from_none_is_silent(self):
        src = (
            "def f(t):\n    try:\n        return int(t)\n"
            "    except ValueError:\n        raise TypeError('bad') from None\n"
        )
        self.assertNotIn("raise-without-from-in-except", shapes(src))

    def test_bare_reraise_is_silent(self):
        src = "def f(t):\n    try:\n        return int(t)\n    except ValueError:\n        raise\n"
        self.assertNotIn("raise-without-from-in-except", shapes(src))

    def test_reraising_caught_name_is_silent(self):
        src = (
            "def f(t):\n    try:\n        return int(t)\n"
            "    except ValueError as err:\n        raise err\n"
        )
        self.assertNotIn("raise-without-from-in-except", shapes(src))


if __name__ == "__main__":
    unittest.main()
