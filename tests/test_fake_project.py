"""fake_project: an "inside_project" consumer of the keep/undef tool.

The fake project header uses the FP prefix for its public configuration, but its
``fake_config.h`` leaks non-standard ``HAVE_*`` macros.  The suite generates
``fake_project_keep.h`` / ``fake_project_undef.h`` with ``inside_project=True``
and then verifies:

* the same macro/identifier three-scenario tests hold (using ``fake_config.h``
  as the polluting header and ``fake_project.h`` as the self-wrapping header),
* the target functions declared by fake_functions.h still enter user code space,
* the internal control macros (HAVE_*) do NOT leak into user code space,
* the standard FP_* / FAKE_* macros survive untouched.

The three scenarios mirror the pyconfig.h tests but are scoped to the project:

  1. ``#define HAVE_FORK 42`` (or ``int HAVE_FORK;``) with no header  -> OK
  2. including ``fake_config.h`` directly                          -> FAILS / clobbered
  3. including the self-wrapping ``fake_project.h``                -> OK again
"""

import random

from unittest_helpers import (
    FAKE_PROJECT_DIR,
    compile_c,
    generate_fake_project_headers,
    is_fp_standard,
    PythonHeadersTestCase,
)

HAVE_MACROS = ("HAVE_FORK", "HAVE_PIPE", "HAVE_UNISTD_H")


def _compile(src, extra_include_dirs=()):
    return compile_c(src, include_dirs=[FAKE_PROJECT_DIR, *extra_include_dirs])


class TestFakeProjectGeneration(PythonHeadersTestCase):
    """Generation / rule basics."""

    def test_generate_fake_project_headers(self):
        out = self.make_tmpdir()
        generate_fake_project_headers(out)
        self.assertTrue((out / "fake_project_keep.h").exists())
        self.assertTrue((out / "fake_project_undef.h").exists())

    def test_fp_prefix_standard_rule(self):
        self.assertTrue(is_fp_standard("FP_ENABLE_FEATURE_A"))
        self.assertTrue(is_fp_standard("FAKE_PROJECT_H"))
        self.assertFalse(is_fp_standard("HAVE_FORK"))

    def test_only_have_macros_are_undefed(self):
        """fake_config.h: FP_* / FAKE_* kept, HAVE_* stripped."""
        out = self.make_tmpdir()
        generate_fake_project_headers(out)
        undef = (out / "fake_project_undef.h").read_text(encoding="utf-8")
        keep = (out / "fake_project_keep.h").read_text(encoding="utf-8")

        for m in HAVE_MACROS:
            self.assertIn(m, undef)
            self.assertIn(m, keep)
        for m in ("FP_ENABLE_FEATURE_A", "FP_VERSION_MAJOR", "FP_BUFFER_SIZE"):
            self.assertNotIn(m, undef)
        self.assertNotIn("FAKE_PROJECT_H", undef)

    def test_inside_project_headers_have_no_order_guards(self):
        """inside_project=True drops the 'must be before/after Python.h' guards."""
        out = self.make_tmpdir()
        generate_fake_project_headers(out)
        keep = (out / "fake_project_keep.h").read_text(encoding="utf-8")
        undef = (out / "fake_project_undef.h").read_text(encoding="utf-8")
        self.assertNotIn("must be included *before*", keep)
        self.assertNotIn("must be included *after*", undef)


class TestFakeProjectScenarios(PythonHeadersTestCase):
    """"Same three scenarios" — macro and variable/identifier layers."""

    def test_macro_layer_three_scenarios(self):
        """Macro layer: (1) define w/o header, (2) fail via fake_config.h,
        (3) restored via self-wrapping fake_project.h."""
        out = self.make_tmpdir()
        generate_fake_project_headers(out)
        macro = random.Random(5).choice(HAVE_MACROS)

        s1 = (
            f"#define {macro} 42\n"
            f"#if {macro} != 42\n#error MACRO_CLOBBERED\n#endif\n"
            "int main(void){return 0;}\n"
        )
        r1 = _compile(s1, [out])
        self.assertTrue(r1.ok, f"[{macro}] step1 should compile:\n{r1.stderr}")

        s2 = (
            f"#define {macro} 42\n"
            '#include "fake_config.h"\n'
            f"#if {macro} != 42\n#error MACRO_CLOBBERED\n#endif\n"
            "int main(void){return 0;}\n"
        )
        r2 = _compile(s2, [out])
        self.assertFalse(r2.ok and "MACRO_CLOBBERED" not in r2.stderr,
                         f"[{macro}] step2 (fake_config.h) should clobber the macro:\n{r2.stderr}")
        self.assertIn("MACRO_CLOBBERED", r2.stderr)

        s3 = (
            f"#define {macro} 42\n"
            '#include "fake_project.h"\n'
            f"#if {macro} != 42\n#error MACRO_CLOBBERED\n#endif\n"
            "int main(void){return 0;}\n"
        )
        r3 = _compile(s3, [out])
        self.assertTrue(r3.ok, f"[{macro}] step3 (fake_project.h) should restore value:\n{r3.stderr}")

    def test_variable_layer_three_scenarios(self):
        """Variable layer: (1) identifier w/o header, (2) fail via fake_config.h,
        (3) restored via self-wrapping fake_project.h."""
        out = self.make_tmpdir()
        generate_fake_project_headers(out)
        macro = random.Random(6).choice(HAVE_MACROS)

        s1 = f"int {macro} = 7;\nint main(void){{return {macro} == 7 ? 0 : 1;}}\n"
        r1 = _compile(s1, [out])
        self.assertTrue(r1.ok, f"[{macro}] step1 variable should compile:\n{r1.stderr}")

        s2 = (
            '#include "fake_config.h"\n'
            f"int {macro} = 7;\n"
            "int main(void){return 0;}\n"
        )
        r2 = _compile(s2, [out])
        self.assertFalse(r2.ok, f"[{macro}] step2 variable (fake_config.h) should fail:\n{r2.stderr}")

        s3 = (
            '#include "fake_project.h"\n'
            f"int {macro} = 7;\n"
            f"int main(void){{return {macro} == 7 ? 0 : 1;}}\n"
        )
        r3 = _compile(s3, [out])
        self.assertTrue(r3.ok, f"[{macro}] step3 variable (fake_project.h) should compile:\n{r3.stderr}")


class TestFakeProjectGuarantees(PythonHeadersTestCase):
    """"Does not affect the internal project" guarantees."""

    def test_target_functions_enter_user_space(self):
        """Target functions declared via conditional compile must still be visible."""
        out = self.make_tmpdir()
        generate_fake_project_headers(out)
        src = (
            '#include "fake_project.h"\n'
            "int main(void){\n"
            "    int (*a)(void) = fp_always_available;\n"
            "    int (*b)(void) = fp_feature_a_enabled;\n"
            "    int (*c)(void) = fp_has_fork_support;\n"
            "    (void)a; (void)b; (void)c;\n"
            "    return 0;\n"
            "}\n"
        )
        r = _compile(src, [out])
        self.assertTrue(r.ok, f"target functions should be declared:\n{r.stderr}")

    def test_internal_have_macros_do_not_leak(self):
        """The controlling HAVE_* macros must NOT appear in user code space."""
        out = self.make_tmpdir()
        generate_fake_project_headers(out)
        guards = "".join(
            f"#ifdef {m}\n#error {m}_LEAKED\n#endif\n" for m in HAVE_MACROS
        )
        src = '#include "fake_project.h"\n' + guards + "int main(void){return 0;}\n"
        r = _compile(src, [out])
        self.assertTrue(r.ok, f"HAVE_* macros must not leak into user code:\n{r.stderr}")

    def test_fp_public_macros_still_visible(self):
        """Standard FP_* macros must survive the project header."""
        out = self.make_tmpdir()
        generate_fake_project_headers(out)
        src = (
            '#include "fake_project.h"\n'
            "#ifndef FP_ENABLE_FEATURE_A\n"
            '#error FP_ENABLE_FEATURE_A_MISSING\n'
            "#endif\n"
            "#if FP_BUFFER_SIZE != 256\n"
            '#error FP_BUFFER_SIZE_WRONG\n'
            "#endif\n"
            "int main(void){return 0;}\n"
        )
        r = _compile(src, [out])
        self.assertTrue(r.ok, f"FP_* macros must remain visible:\n{r.stderr}")

    def test_fake_project_still_compatible_with_python(self):
        """The self-wrapping project can still coexist with Python.h using the
        Python keep/undef sandwich (integration sanity check)."""
        out = self.make_tmpdir()
        generate_fake_project_headers(out)
        src = (
            '#include "fake_project.h"\n'
            "#include <Python_keep.h>\n"
            "#include <Python.h>\n"
            "#include <Python_undef.h>\n"
            "int main(void){return 0;}\n"
        )
        r = _compile(src, [out, self.python_include_dir, self.generated_headers])
        self.assertTrue(r.ok, f"fake_project + Python sandwich should compile:\n{r.stderr}")


if __name__ == "__main__":
    import unittest

    unittest.main()
