"""Functional tests of the compiled Fortran 2018 drivers in build/bin (book data cards on stdin)."""

from conftest import (
    BAIRSTOW_CARD,
    BISECTION_CARD,
    LAGRANGE_CARD,
    ROMBERG_CARD,
    SIMPSON_CARD,
    run_driver,
    trace_records,
)


class TestBisectionDriver:
    def test_driver_bisection_book_card(self, evidence):
        res = run_driver("ch01_p01_bisection", BISECTION_CARD)
        evidence(stdout=res.stdout, stderr=res.stderr, exit_code=res.returncode, stdin=BISECTION_CARD)
        assert res.returncode == 0
        rows = [line for line in res.stdout.splitlines() if line.strip().startswith("AT X")]
        assert len(rows) == 15
        assert "THE VALUE, X =   .4435729 IS A ROOT.  15 ITERATIONS WERE REQUIRED." in res.stdout

    def test_driver_bisection_trace(self, evidence):
        res = run_driver("ch01_p01_bisection", BISECTION_CARD, "--trace")
        evidence(stdout=res.stdout, exit_code=res.returncode, stdin=BISECTION_CARD)
        assert res.returncode == 0
        steps = trace_records(res.stdout, "STEP")
        result = trace_records(res.stdout, "RESULT")
        assert len(steps) == 15
        assert len(result) == 1
        assert abs(float(result[0]["value"]) - 0.4435729) < 1e-6
        assert result[0]["iterations"] == "15"
        assert result[0]["converged"] == "T"

    def test_driver_bisection_no_sign_change(self, evidence):
        card = "0. 0.3 1.E-5\n"
        book = run_driver("ch01_p01_bisection", card)
        trace = run_driver("ch01_p01_bisection", card, "--trace")
        evidence(stdout=book.stdout + trace.stdout, exit_code=book.returncode,
                 trace_exit_code=trace.returncode, stdin=card)
        assert book.returncode == 1
        assert "NOT OF OPPOSITE SIGNS" in book.stdout
        assert trace.returncode == 2
        assert trace_records(trace.stdout, "ERROR")[0]["code"] == "BRACKET"

    def test_driver_bisection_non_convergent(self, evidence):
        card = "0. 1. 1.E-30\n"
        book = run_driver("ch01_p01_bisection", card)
        trace = run_driver("ch01_p01_bisection", card, "--trace")
        evidence(stdout=book.stdout[-200:] + trace.stdout[-200:], exit_code=book.returncode,
                 trace_exit_code=trace.returncode, stdin=card)
        assert book.returncode == 1
        assert "NON-CONVERGENT IN 25 ITERATIONS." in book.stdout
        assert trace.returncode == 2
        assert len(trace_records(trace.stdout, "STEP")) == 25
        assert trace_records(trace.stdout, "ERROR")[0]["code"] == "NON_CONVERGENT"

    def test_driver_bisection_unknown_preset(self, evidence):
        res = run_driver("ch01_p01_bisection", BISECTION_CARD, "--trace", "--preset", "9")
        evidence(stdout=res.stdout, stderr=res.stderr, exit_code=res.returncode, stdin=BISECTION_CARD)
        assert res.returncode == 2
        assert trace_records(res.stdout, "ERROR")[0]["code"] == "INPUT"

    def test_driver_bisection_preset_cubic(self, evidence):
        card = "1. 2. 1.E-6\n"
        res = run_driver("ch01_p01_bisection", card, "--trace", "--preset", "2")
        evidence(stdout=res.stdout[-400:], exit_code=res.returncode, stdin=card)
        assert res.returncode == 0
        value = float(trace_records(res.stdout, "RESULT")[0]["value"])
        assert abs(value**3 - value - 1) <= 1e-6

    def test_driver_bisection_malformed_card(self, evidence):
        card = "abc\n"
        res = run_driver("ch01_p01_bisection", card)
        evidence(stdout=res.stdout, stderr=res.stderr, exit_code=res.returncode, stdin=card)
        assert res.returncode == 1
        assert res.stderr.strip() != ""


class TestBairstowDriver:
    def test_driver_bairstow_book_card(self, evidence):
        res = run_driver("ch01_p02_bairstow", BAIRSTOW_CARD)
        evidence(stdout=res.stdout, exit_code=res.returncode, stdin=BAIRSTOW_CARD)
        assert res.returncode == 0
        assert "THE QUADRATIC FACTORS ARE-" in res.stdout
        assert "4.19999 X +   -2.09999" in res.stdout
        assert "3.30000 X +   -6.20000" in res.stdout
        assert "1.00000X +  -10.30000" in res.stdout

    def test_driver_bairstow_trace_factors(self, evidence):
        res = run_driver("ch01_p02_bairstow", BAIRSTOW_CARD, "--trace")
        evidence(stdout="\n".join(l for l in res.stdout.splitlines() if not l.startswith("STEP")),
                 exit_code=res.returncode, stdin=BAIRSTOW_CARD)
        assert res.returncode == 0
        factors = trace_records(res.stdout, "FACTOR")
        quads = [(float(f["r"]), float(f["s"])) for f in factors if f["kind"] == "quadratic"]
        linear = [(float(f["a1"]), float(f["a0"])) for f in factors if f["kind"] == "linear"]
        assert len(quads) == 2 and len(linear) == 1
        assert abs(quads[0][0] - 4.2) < 1e-4 and abs(quads[0][1] + 2.1) < 1e-4
        assert abs(quads[1][0] - 3.3) < 1e-4 and abs(quads[1][1] + 6.2) < 1e-4
        assert abs(linear[0][0] - 1.0) < 1e-6 and abs(linear[0][1] + 10.3) < 1e-4

    def test_driver_bairstow_sample_input_file(self, evidence):
        from conftest import REPO_ROOT

        card = (REPO_ROOT / "sample_input.txt").read_text()
        res = run_driver("ch01_p02_bairstow", card)
        evidence(stdout=res.stdout, exit_code=res.returncode, stdin=card)
        assert res.returncode == 0
        assert "4.19999 X +   -2.09999" in res.stdout

    def test_driver_bairstow_non_convergent(self, evidence):
        card = "0. 1. -17.8 99.41 -261.218 352.611 -134.106\n0. 0. 1.E-5 2 5\n"
        book = run_driver("ch01_p02_bairstow", card)
        trace = run_driver("ch01_p02_bairstow", card, "--trace")
        evidence(stdout=book.stdout[-200:] + trace.stdout[-200:], exit_code=book.returncode,
                 trace_exit_code=trace.returncode, stdin=card)
        assert book.returncode == 1
        assert "DOES NOT CONVERGE AFTER    2 ITERATIONS" in book.stdout
        assert trace.returncode == 2
        assert trace_records(trace.stdout, "ERROR")[0]["code"] == "NON_CONVERGENT"

    def test_driver_bairstow_degree_error(self, evidence):
        card = "0. 1. -17.8 99.41 -261.218 352.611 -134.106\n0. 0. 1.E-5 20 7\n"
        res = run_driver("ch01_p02_bairstow", card, "--trace")
        evidence(stdout=res.stdout, exit_code=res.returncode, stdin=card)
        assert res.returncode == 2
        assert trace_records(res.stdout, "ERROR")[0]["code"] == "DEGREE"

    def test_driver_bairstow_verbose(self, evidence):
        res = run_driver("ch01_p02_bairstow", BAIRSTOW_CARD, "--verbose")
        evidence(stdout=res.stdout, exit_code=res.returncode, stdin=BAIRSTOW_CARD)
        assert res.returncode == 0
        base = run_driver("ch01_p02_bairstow", BAIRSTOW_CARD).stdout
        assert res.stdout.startswith(base.rstrip("\n")[:200])
        assert len(res.stdout) > len(base)


class TestSimpsonDriver:
    def test_driver_simpson_book_card(self, evidence):
        res = run_driver("ch03_p01_simpson", SIMPSON_CARD)
        evidence(stdout=res.stdout, exit_code=res.returncode, stdin=SIMPSON_CARD)
        assert res.returncode == 0
        assert "VALUE OF SINE INTEGRAL FROM X = 0 TO X =  5.00 IS 1.5499312 WITH 100 PANELS" in res.stdout

    def test_driver_simpson_odd_panels(self, evidence):
        card = "5.0 99\n"
        book = run_driver("ch03_p01_simpson", card)
        trace = run_driver("ch03_p01_simpson", card, "--trace")
        evidence(stdout=book.stdout + trace.stdout, exit_code=book.returncode,
                 trace_exit_code=trace.returncode, stdin=card)
        assert book.returncode == 1
        assert "ODD NUMBER OF PANELS" in book.stdout
        assert trace.returncode == 2
        assert trace_records(trace.stdout, "ERROR")[0]["code"] == "ODD_PANELS"


class TestRombergDriver:
    def test_driver_romberg_book_card(self, evidence):
        res = run_driver("ch03_p02_romberg", ROMBERG_CARD)
        evidence(stdout=res.stdout, exit_code=res.returncode, stdin=ROMBERG_CARD)
        assert res.returncode == 0
        assert "VALUE IS  1.6181944" in res.stdout
        assert "80 SUBINTERVALS WERE REQUIRED TO MEET TOLERANCE OF  2.0000000E-07" in res.stdout
        table = [l for l in res.stdout.splitlines() if l.strip().startswith("1.6")]
        assert [len(l.split()) for l in table] == [1, 2, 3, 4]

    def test_driver_romberg_trace_table(self, evidence):
        res = run_driver("ch03_p02_romberg", ROMBERG_CARD, "--trace")
        evidence(stdout=res.stdout, exit_code=res.returncode, stdin=ROMBERG_CARD)
        assert res.returncode == 0
        assert len(trace_records(res.stdout, "TABLE")) == 10
        result = trace_records(res.stdout, "RESULT")[0]
        assert result["subintervals"] == "80" and result["converged"] == "T"
        assert abs(float(result["value"]) - 1.6181944) < 1e-6

    def test_driver_romberg_not_converged(self, evidence):
        card = "15.0 -1.\n"
        book = run_driver("ch03_p02_romberg", card)
        trace = run_driver("ch03_p02_romberg", card, "--trace")
        evidence(stdout=book.stdout[-300:] + trace.stdout[-200:], exit_code=book.returncode,
                 trace_exit_code=trace.returncode, stdin=card)
        assert book.returncode == 0
        assert "BUT DID NOT MEET TOLERANCE" in book.stdout
        result = trace_records(trace.stdout, "RESULT")[0]
        assert trace.returncode == 0
        assert result["converged"] == "F" and result["iterations"] == "8"
        assert result["subintervals"] == "2560"


class TestLagrangeDriver:
    def test_driver_lagrange_book_card(self, evidence):
        res = run_driver("lagrange_interpolation", LAGRANGE_CARD)
        evidence(stdout=res.stdout, exit_code=res.returncode, stdin=LAGRANGE_CARD)
        assert res.returncode == 0
        assert "AMONG   5 VALUES" in res.stdout
        assert "AT X =      5.000 THE FUNCTION HAS VALUE OF     2.3119" in res.stdout

    def test_driver_lagrange_duplicate_x(self, evidence):
        card = "3\n1 1\n1 2\n3 3\n2\n"
        book = run_driver("lagrange_interpolation", card)
        trace = run_driver("lagrange_interpolation", card, "--trace")
        evidence(stdout=book.stdout + book.stderr + trace.stdout, exit_code=book.returncode,
                 trace_exit_code=trace.returncode, stdin=card)
        assert book.returncode == 1
        assert trace.returncode == 2
        assert trace_records(trace.stdout, "ERROR")[0]["code"] == "INPUT"

    def test_driver_lagrange_count_mismatch(self, evidence):
        card = "5\n1 1\n2 2\n3\n"
        res = run_driver("lagrange_interpolation", card, "--trace")
        evidence(stdout=res.stdout, exit_code=res.returncode, stdin=card)
        assert res.returncode == 2
        assert trace_records(res.stdout, "ERROR")[0]["code"] == "INPUT"


class TestDriverHelp:
    def test_driver_help_all(self, evidence):
        outs = []
        for name in ("ch01_p01_bisection", "ch01_p02_bairstow", "ch03_p01_simpson",
                     "ch03_p02_romberg", "lagrange_interpolation"):
            res = run_driver(name, "", "--help")
            outs.append((name, res.returncode, res.stdout.splitlines()[0] if res.stdout else ""))
            assert res.returncode == 0, name
            assert f"usage: {name}" in res.stdout
            assert "--trace" in res.stdout
        evidence(stdout="\n".join(f"{n} rc={c}: {l}" for n, c, l in outs), exit_code=0)
