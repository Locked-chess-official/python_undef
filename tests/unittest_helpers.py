"""Shared helpers and base :class:`unittest.TestCase` for the python_undef suite.

The suite needs a real C compiler plus a config header (normally the running
interpreter's ``pyconfig.h``) so that it can exercise the actual keep/undef
header behaviour against the *config file itself* -- the same file the tool's
default generation analyses.  We deliberately do NOT depend on what other
standard/system headers happen to define, so the same suite works on Windows,
macOS and Linux with the same expectations.
"""

import os
import re
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
FAKE_PROJECT_DIR = Path(__file__).resolve().parent / "fake_project"

# Make the in-tree package importable without installing it.
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import python_undef  # noqa: E402


def _which(*names):
    for name in names:
        path = shutil.which(name)
        if path:
            return path
    return None


CC = os.environ.get("CC") or _which("cc", "gcc", "clang")

# The single config file the tool's default generation analyses.
PYCONFIG = Path(sysconfig.get_path("include")) / "pyconfig.h"


class CResult:
    """Result of a C compilation attempt."""

    def __init__(self, ok, stderr):
        self.ok = ok
        self.stderr = stderr

    def __bool__(self):
        return self.ok


def _require_cc():
    """Raise SkipTest when no usable C compiler is present."""
    if CC is None:
        raise unittest.SkipTest("no C compiler (cc/gcc/clang) found")


def compile_c(source, include_dirs=(), defines=(), extra_flags=()):
    """Compile a C snippet (syntax-only). Returns a :class:`CResult`."""
    _require_cc()
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "probe.c"
        src.write_text(source, encoding="utf-8")
        cmd = [CC, "-fsyntax-only", "-x", "c", str(src)]
        for d in include_dirs:
            cmd += ["-I", str(d)]
        for d in defines:
            cmd += ["-D", str(d)]
        cmd += list(extra_flags)
        proc = subprocess.run(cmd, capture_output=True, text=True)
        return CResult(proc.returncode == 0, proc.stderr)


def _preprocess_dM(source, include_dirs=()):
    """Run the preprocessor and return ``{macro: value_token}`` for all defined macros."""
    _require_cc()
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "probe.c"
        src.write_text(source, encoding="utf-8")
        cmd = [CC, "-E", "-dM", "-x", "c", str(src)]
        for d in include_dirs:
            cmd += ["-I", str(d)]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise AssertionError(f"preprocessor failed:\n{proc.stderr}")
    defined = {}
    for line in proc.stdout.splitlines():
        parts = line.split(None, 2)
        if len(parts) >= 2 and parts[0] == "#define":
            defined[parts[1]] = parts[2] if len(parts) == 3 else ""
    return defined


# --------------------------------------------------------------------------- #
# Macro inspection helpers (reusing the tool's own parsing rules)
# --------------------------------------------------------------------------- #

def non_standard_macros(path=None):
    """Collect the non-standard macros from a config/pyconfig file, per the tool."""
    path = path or PYCONFIG
    result = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            name = python_undef._extract_macro_name(line)
            if name and not python_undef._is_standard_python_macro(name):
                result.append(name)
    return sorted(set(result))


def macros_after_config(config_path):
    """Return ``{macro: value}`` for everything defined by ``#include <config>``
    (the config file itself, plus anything it pulls in -- but the config file
    is the only header we point the compiler at)."""
    return _preprocess_dM(
        f"#include <{config_path.name}>\nint main(void){{return 0;}}\n",
        [str(config_path.parent)],
    )


def macros_after_python(python_include_dir):
    """Return ``{macro: value}`` for everything defined by ``#include <Python.h>``."""
    return _preprocess_dM(
        "#include <Python.h>\nint main(void){return 0;}\n",
        [str(python_include_dir)],
    )


def macro_appears_without_processing(macro, header, include_dirs):
    """Does ``macro`` get defined just by including ``header`` (the config file
    itself) with no other handling?  This is spec step (2), anchored to the
    config file only, so it holds on every platform."""
    src = (
        f"#include <{header}>\n"
        f"#ifdef {macro}\n"
        "/* appears */\n"
        "#else\n"
        '#error MACRO_DOES_NOT_APPEAR\n'
        "#endif\n"
        "int main(void){return 0;}\n"
    )
    return compile_c(src, include_dirs).ok


def pick_macro(rng, nonstd, validator, header="pyconfig.h", include_dirs=None):
    """Randomly select a non-standard macro.

    * It must actually appear after including ``header`` (the config file, spec
      step 2); macros that do not appear there are excluded.
    * It must satisfy ``validator(macro)`` (e.g. genuinely clobbered, or
      genuinely breaks as an identifier).
    """
    if include_dirs is None:
        include_dirs = [str(PYCONFIG.parent)]
    pool = list(nonstd)
    rng.shuffle(pool)
    for m in pool:
        if not macro_appears_without_processing(m, header, include_dirs):
            continue  # exclude: this macro does not actually exist here
        if validator(m, header, include_dirs):
            return m
    raise AssertionError("no suitable non-standard macro found")


# --------------------------------------------------------------------------- #
# Negative-compile validators (used to keep the random pick robust)
# --------------------------------------------------------------------------- #

def macro_is_clobbered(macro, header, include_dirs):
    """True if pre-defining ``macro`` to 42 then including ``header`` clobbers it."""
    src = (
        f"#define {macro} 42\n"
        f"#include <{header}>\n"
        f"#if {macro} != 42\n"
        '#error MACRO_CLOBBERED\n'
        "#endif\n"
        "int main(void){return 0;}\n"
    )
    r = compile_c(src, include_dirs)
    return (not r.ok) and "MACRO_CLOBBERED" in r.stderr


def macro_breaks_identifier(macro, header, include_dirs):
    """True if using ``macro`` as a plain identifier breaks after including ``header``."""
    src = (
        f"#include <{header}>\n"
        f"int {macro} = 7;\n"
        "int main(void){return 0;}\n"
    )
    return not compile_c(src, include_dirs).ok


# --------------------------------------------------------------------------- #
# Three-step scenario runners (macro layer + identifier/variable layer)
# --------------------------------------------------------------------------- #

def run_macro_layer(macro, main_header, main_include_dirs,
                    keep_undef_include_dirs, keep_header, undef_header, value="42"):
    """Verify the three macro-layer scenarios.

    1. ``#define <macro> value`` with no other header  -> compiles.
    2. ``#define <macro> value`` + include main header  -> FAILS (clobbered).
    3. keep / main / undef sandwich                    -> compiles (restored).
    """
    sandwich_dirs = list(keep_undef_include_dirs) + list(main_include_dirs)

    s1 = (
        f"#define {macro} {value}\n"
        f"#if {macro} != {value}\n#error MACRO_CLOBBERED\n#endif\n"
        "int main(void){return 0;}\n"
    )
    r1 = compile_c(s1, [])
    if not r1.ok:
        raise AssertionError(f"[{macro}] step1 (no header) should compile:\n{r1.stderr}")

    s2 = (
        f"#define {macro} {value}\n"
        f"#include <{main_header}>\n"
        f"#if {macro} != {value}\n#error MACRO_CLOBBERED\n#endif\n"
        "int main(void){return 0;}\n"
    )
    r2 = compile_c(s2, main_include_dirs)
    if r2.ok or "MACRO_CLOBBERED" not in r2.stderr:
        raise AssertionError(
            f"[{macro}] step2 (with {main_header}) should be clobbered:\n{r2.stderr}"
        )

    s3 = (
        f"#define {macro} {value}\n"
        f"#include <{keep_header}>\n"
        f"#include <{main_header}>\n"
        f"#include <{undef_header}>\n"
        f"#if {macro} != {value}\n#error MACRO_CLOBBERED\n#endif\n"
        "int main(void){return 0;}\n"
    )
    r3 = compile_c(s3, sandwich_dirs)
    if not r3.ok:
        raise AssertionError(f"[{macro}] step3 (sandwich) should restore value:\n{r3.stderr}")


def run_variable_layer(macro, main_header, main_include_dirs,
                       keep_undef_include_dirs, keep_header, undef_header):
    """Verify the three identifier/variable-layer scenarios.

    1. ``int <macro> = 7;`` with no header          -> compiles.
    2. include main header then ``int <macro> = 7;`` -> FAILS (macro expands).
    3. keep / main / undef sandwich                  -> compiles (macro removed).
    """
    sandwich_dirs = list(keep_undef_include_dirs) + list(main_include_dirs)

    s1 = f"int {macro} = 7;\nint main(void){{return {macro} == 7 ? 0 : 1;}}\n"
    r1 = compile_c(s1, [])
    if not r1.ok:
        raise AssertionError(f"[{macro}] step1 variable should compile:\n{r1.stderr}")

    s2 = f"#include <{main_header}>\nint {macro} = 7;\nint main(void){{return 0;}}\n"
    r2 = compile_c(s2, main_include_dirs)
    if r2.ok:
        raise AssertionError(
            f"[{macro}] step2 variable (with {main_header}) should fail:\n{r2.stderr}"
        )

    s3 = (
        f"#include <{keep_header}>\n"
        f"#include <{main_header}>\n"
        f"#include <{undef_header}>\n"
        f"int {macro} = 7;\n"
        f"int main(void){{return {macro} == 7 ? 0 : 1;}}\n"
    )
    r3 = compile_c(s3, sandwich_dirs)
    if not r3.ok:
        raise AssertionError(f"[{macro}] step3 variable (sandwich) should compile:\n{r3.stderr}")


# --------------------------------------------------------------------------- #
# fake_project helpers
# --------------------------------------------------------------------------- #

def is_fp_standard(macro_name):
    """Standard-rule for the fake project: FP_* (public) and FAKE_* (guards)."""
    return macro_name.startswith(("FP", "FAKE_"))


def generate_fake_project_headers(output_dir):
    """Generate fake_project_keep.h / fake_project_undef.h from fake_config.h."""
    ok = python_undef.generate_python_undef_header(
        str(FAKE_PROJECT_DIR / "fake_config.h"),
        output_path=str(output_dir),
        project_name="fake_project",
        main_header_macro="FAKE_PROJECT_H",
        main_header_name="fake_project.h",
        macro_need_header="FP",
        is_standard_macro_rule=is_fp_standard,
        inside_project=True,
    )
    if not ok:
        raise AssertionError("failed to generate fake_project keep/undef headers")
    return output_dir


# --------------------------------------------------------------------------- #
# Base test cases
# --------------------------------------------------------------------------- #

class BaseTestCase(unittest.TestCase):
    """Base class: skips when no C toolchain / pyconfig.h is available."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if CC is None:
            raise unittest.SkipTest("C compiler (cc/gcc/clang) not available")
        if not PYCONFIG.exists():
            raise unittest.SkipTest(
                f"pyconfig.h not found at {PYCONFIG} (need python dev headers)"
            )

    def make_tmpdir(self):
        """A per-test temporary directory that is cleaned up automatically."""
        d = tempfile.mkdtemp(prefix="python_undef_test_")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        return Path(d)


class PythonHeadersTestCase(BaseTestCase):
    """Base class that also generates Python_keep.h / Python_undef.h once per class."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.python_include_dir = PYCONFIG.parent
        cls.nonstd_macros = non_standard_macros()
        cls._gen_tmpdir = tempfile.mkdtemp(prefix="generated_python_headers_")
        ok = python_undef.generate_python_undef_header(
            str(PYCONFIG), output_path=cls._gen_tmpdir
        )
        if not ok:
            shutil.rmtree(cls._gen_tmpdir, ignore_errors=True)
            raise AssertionError("failed to generate Python_keep.h / Python_undef.h")
        cls.generated_headers = Path(cls._gen_tmpdir)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls._gen_tmpdir, ignore_errors=True)
        super().tearDownClass()
