"""Step 1: normal generation of Python_keep.h / Python_undef.h.

These tests exercise ``generate_python_undef_header`` against the running
interpreter's ``pyconfig.h`` and assert that the two headers are produced with
sane, matching content.
"""

import re

from unittest_helpers import PYCONFIG, non_standard_macros, python_undef, BaseTestCase


class TestGenerate(BaseTestCase):
    def test_generate_produces_both_headers(self):
        out = self.make_tmpdir()
        ok = python_undef.generate_python_undef_header(str(PYCONFIG), output_path=str(out))
        self.assertIs(ok, True)
        self.assertTrue((out / "Python_keep.h").exists())
        self.assertTrue((out / "Python_undef.h").exists())

    def test_generate_headers_are_nonempty(self):
        out = self.make_tmpdir()
        python_undef.generate_python_undef_header(str(PYCONFIG), output_path=str(out))
        keep = (out / "Python_keep.h").read_text(encoding="utf-8")
        undef = (out / "Python_undef.h").read_text(encoding="utf-8")
        self.assertGreater(len(keep), 0)
        self.assertGreater(len(undef), 0)

    def test_keep_and_undef_cover_the_same_macros(self):
        """Every macro handled by the undef header must have a counterpart in keep."""
        out = self.make_tmpdir()
        python_undef.generate_python_undef_header(str(PYCONFIG), output_path=str(out))
        keep = (out / "Python_keep.h").read_text(encoding="utf-8")
        undef = (out / "Python_undef.h").read_text(encoding="utf-8")

        keep_macros = set(re.findall(r"push_macro\(\"([^\"]+)\"\)", keep))
        undef_macros = set(re.findall(r"pop_macro\(\"([^\"]+)\"\)", undef))
        self.assertTrue(keep_macros)
        self.assertTrue(undef_macros)
        self.assertEqual(keep_macros, undef_macros)

    def test_keep_must_be_included_before_python_h(self):
        """Python_keep.h carries a guard error if Python.h was already included."""
        out = self.make_tmpdir()
        python_undef.generate_python_undef_header(str(PYCONFIG), output_path=str(out))
        keep = (out / "Python_keep.h").read_text(encoding="utf-8")
        self.assertIn("must be included *before* Python.h", keep)

    def test_undef_must_be_included_after_python_h(self):
        out = self.make_tmpdir()
        python_undef.generate_python_undef_header(str(PYCONFIG), output_path=str(out))
        undef = (out / "Python_undef.h").read_text(encoding="utf-8")
        self.assertIn("must be included *after* Python.h", undef)

    def test_nonstandard_macros_exist(self):
        """pyconfig.h really does carry non-standard macros (sanity for the suite)."""
        nonstd = non_standard_macros()
        self.assertTrue(nonstd, "expected pyconfig.h to contain non-standard macros")


if __name__ == "__main__":
    import unittest

    unittest.main()
