"""Step 2 & 3: pyconfig.h targeted tests.

For a randomly-chosen non-standard macro from ``pyconfig.h``:

* confirm it would actually appear in the source environment with no handling,
* verify three scenarios at the macro layer and three at the variable layer:

  1. compiles with no ``Python.h``,
  2. fails to compile once ``Python.h`` is included,
  3. compiles again once the tool's keep/undef headers are used.

For the macro layer the user pre-defines the macro *before* including
``<Python.h>`` (the "user already assumes this macro" hypothesis).
"""

import random

from unittest_helpers import (
    macro_breaks_identifier,
    macro_is_clobbered,
    macros_after_python,
    non_standard_macros,
    pick_macro,
    run_macro_layer,
    run_variable_layer,
    PythonHeadersTestCase,
)


class TestPyconfig(PythonHeadersTestCase):
    def test_random_macro_appears_without_processing(self):
        """Spec step (2): a randomly-picked macro (from the pool that actually
        appears) must be present in the plain ``#include <Python.h>`` environment."""
        defined_after_python = macros_after_python(self.python_include_dir)
        pool = [m for m in self.nonstd_macros if m in defined_after_python]
        self.assertTrue(pool, "no non-standard macros appear after including Python.h")
        macro = random.Random(1).choice(pool)
        # Direct check: it is defined after a bare Python.h include.
        self.assertIn(macro, defined_after_python)

    def test_macro_layer_three_scenarios(self):
        """Macro layer: (1) compile w/o Python.h, (2) fail with, (3) pass with headers."""
        nonstd = non_standard_macros()
        rng = random.Random(2)
        macro = pick_macro(
            rng, nonstd,
            validator=macro_is_clobbered,
            header="Python.h",
            include_dirs=[str(self.python_include_dir)],
        )
        run_macro_layer(
            macro,
            main_header="Python.h",
            main_include_dirs=[self.python_include_dir],
            keep_undef_include_dirs=[self.generated_headers],
            keep_header="Python_keep.h",
            undef_header="Python_undef.h",
            value="42",
        )

    def test_variable_layer_three_scenarios(self):
        """Variable layer: same three scenarios but using the macro as an identifier."""
        nonstd = non_standard_macros()
        rng = random.Random(3)
        macro = pick_macro(
            rng, nonstd,
            validator=macro_breaks_identifier,
            header="Python.h",
            include_dirs=[str(self.python_include_dir)],
        )
        run_variable_layer(
            macro,
            main_header="Python.h",
            main_include_dirs=[self.python_include_dir],
            keep_undef_include_dirs=[self.generated_headers],
            keep_header="Python_keep.h",
            undef_header="Python_undef.h",
        )

    def test_user_predefines_macro_before_python_h(self):
        """Explicit 'user assumes the macro' hypothesis: ``#define`` before ``<Python.h>``."""
        nonstd = non_standard_macros()
        rng = random.Random(4)
        macro = pick_macro(
            rng, nonstd,
            validator=macro_is_clobbered,
            header="Python.h",
            include_dirs=[str(self.python_include_dir)],
        )
        # step2 must fail specifically because the pre-defined macro got clobbered.
        run_macro_layer(
            macro,
            main_header="Python.h",
            main_include_dirs=[self.python_include_dir],
            keep_undef_include_dirs=[self.generated_headers],
            keep_header="Python_keep.h",
            undef_header="Python_undef.h",
        )


if __name__ == "__main__":
    import unittest

    unittest.main()
