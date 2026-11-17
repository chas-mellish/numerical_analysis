"""Functional tests of the real32 (-DSINGLE) Fortran drivers in build/single/bin.

The catalog precision notes say the real32 build matches the book golden values within 1e-6
(Simpson prints 1.5499314, Romberg 1.6181944) and reproduces the bisection/Lagrange/Bairstow
book results.
"""

import re
import subprocess

from conftest import REPO_ROOT, trace_records

SINGLE_BIN = REPO_ROOT / "build" / "single" / "bin"


def run_single(name, card, *flags):
    return subprocess.run([str(SINGLE_BIN / name), *flags], input=card, capture_output=True,
                          text=True, timeout=20, check=False)


class TestSinglePrecisionDrivers:
    def test_single_bisection_book(self, evidence):
        card = "0. 1. 1.E-5\n"
        res = run_single("ch01_p01_bisection", card)
        evidence(stdout=res.stdout, exit_code=res.returncode, stdin=card)
        assert res.returncode == 0
        assert "THE VALUE, X =   .4435729 IS A ROOT.  15 ITERATIONS WERE REQUIRED." in res.stdout

    def test_single_simpson_within_book_tolerance(self, evidence):
        card = "5.0 100\n"
        res = run_single("ch03_p01_simpson", card)
        evidence(stdout=res.stdout, exit_code=res.returncode, stdin=card)
        assert res.returncode == 0
        m = re.search(r"IS (\d\.\d{7}) WITH 100 PANELS", res.stdout)
        assert m, res.stdout
        assert abs(float(m.group(1)) - 1.5499307) <= 1e-6

    def test_single_romberg_within_book_tolerance(self, evidence):
        card = "15.0 2.E-7\n"
        res = run_single("ch03_p02_romberg", card, "--trace")
        evidence(stdout=res.stdout, exit_code=res.returncode, stdin=card)
        assert res.returncode == 0
        result = trace_records(res.stdout, "RESULT")[0]
        assert result["subintervals"] == "80" and result["converged"] == "T"
        assert abs(float(result["value"]) - 1.6181936) <= 1e-6

    def test_single_lagrange_book(self, evidence):
        card = "05\n2.3756 1.6\n3.2682 1.9\n4.4571 2.2\n6.0502 2.5\n8.1919 2.8\n5.0\n"
        res = run_single("lagrange_interpolation", card)
        evidence(stdout=res.stdout, exit_code=res.returncode, stdin=card)
        assert res.returncode == 0
        assert "AT X =      5.000 THE FUNCTION HAS VALUE OF     2.3119" in res.stdout

    def test_single_bairstow_factors(self, evidence):
        card = "0. 1. -17.8 99.41 -261.218 352.611 -134.106\n0. 0. 1.E-5 20 5\n"
        res = run_single("ch01_p02_bairstow", card, "--trace")
        evidence(stdout="\n".join(l for l in res.stdout.splitlines() if not l.startswith("STEP")),
                 exit_code=res.returncode, stdin=card)
        assert res.returncode == 0
        factors = trace_records(res.stdout, "FACTOR")
        quads = [(float(f["r"]), float(f["s"])) for f in factors if f["kind"] == "quadratic"]
        assert abs(quads[0][0] - 4.2) < 1e-4 and abs(quads[0][1] + 2.1) < 1e-4
        assert abs(quads[1][0] - 3.3) < 1e-4 and abs(quads[1][1] + 6.2) < 1e-4
