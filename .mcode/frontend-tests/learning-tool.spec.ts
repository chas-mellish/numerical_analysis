import { test, expect } from "@playwright/test";
import { T, run } from "./helpers";

test.describe("Home", () => {
  test("lists programs by chapter, Lagrange under unconfirmed", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("h1")).toHaveText("Programs");
    await expect(page.getByRole("heading", { name: "Chapter 1: Solution of Nonlinear Equations" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Chapter 3: Numerical Integration" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Book reference unconfirmed" })).toBeVisible();
    for (const n of ["Interval halving (bisection)", "Bairstow quadratic factors", "Simpson's 1/3 rule, Si(B)", "Romberg integration, Si(B)", "Lagrangian interpolation"]) {
      await expect(page.getByRole("link", { name: n })).toBeVisible();
    }
    // Lagrange is in the unconfirmed section, not in a chapter section.
    const unconfirmed = page.locator("section, div").filter({ has: page.getByRole("heading", { name: "Book reference unconfirmed" }) }).last();
    await expect(unconfirmed.getByRole("link", { name: "Lagrangian interpolation" })).toBeVisible();
    await expect(unconfirmed.getByRole("link", { name: "Interval halving (bisection)" })).toHaveCount(0);
  });

  test("card navigates to program page", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("link", { name: "Interval halving (bisection)" }).click();
    await expect(page).toHaveURL(/\/programs\/ch01_p01$/);
    await expect(T(page, "run-button")).toBeVisible();
  });
});

test.describe("Bisection", () => {
  test("book data card prefilled and presets present", async ({ page }) => {
    await page.goto("/programs/ch01_p01");
    await expect(page.locator("#in-x1")).toHaveValue("0.0");
    await expect(page.locator("#in-x2")).toHaveValue("1.0");
    await expect(page.locator("#in-tol")).toHaveValue("1e-05");
    await expect(page.locator("#engine-python")).toBeChecked();
    await expect(page.locator("#function-select option")).toHaveText([
      "1: Book: exp(-x) - sin(pi x / 2)", "2: x^3 - x - 1", "3: cos(x) - x", "Custom expression (Python engine only)",
    ]);
    await expect(T(page, "results-placeholder")).toBeVisible();
  });

  test("python run matches book: .4435729 in 15 iterations", async ({ page }) => {
    await page.goto("/programs/ch01_p01");
    await run(page);
    await expect(T(page, "result-value")).toContainText("0.44357299");
    await expect(T(page, "result-iterations")).toHaveText("15");
    await expect(T(page, "result-converged")).toContainText("yes");
    await expect(T(page, "result-engine")).toContainText("python");
    await expect(T(page, "results-table").locator('[data-testid="step-row"]')).toHaveCount(15);
    await expect(T(page, "book-text")).toContainText("THE VALUE, X =   .4435729 IS A ROOT.  15 ITERATIONS WERE REQUIRED.");
    await expect(page.locator(".js-plotly-plot")).toHaveCount(2);
    await expect(T(page, "chart-bracket")).toBeVisible();
    await expect(T(page, "chart-abs_residual")).toBeVisible();
  });

  test("fortran engine run gives the book result", async ({ page }) => {
    await page.goto("/programs/ch01_p01");
    await run(page, "fortran");
    await expect(T(page, "result-iterations")).toHaveText("15");
    await expect(T(page, "result-engine")).toContainText("fortran");
    await expect(T(page, "book-text")).toContainText(".4435729 IS A ROOT");
  });

  test("compare mode shows agreement and both panes fit at 1280px", async ({ page }) => {
    await page.goto("/programs/ch01_p01");
    await run(page, "compare");
    await expect(T(page, "compare-view")).toBeVisible();
    await expect(T(page, "compare-summary")).toContainText("agree");
    await expect(T(page, "compare-iterations")).toContainText("python 15, fortran 15");
    for (const id of ["compare-max-diff", "compare-value-diff", "compare-python", "compare-fortran"]) {
      await expect(T(page, id)).toBeVisible();
    }
    await expect(T(page, "book-text-python")).toContainText("15 ITERATIONS WERE REQUIRED");
    await expect(T(page, "book-text-fortran")).toContainText("15 ITERATIONS WERE REQUIRED");
    // Fix 55b6cd6: panes must not be clipped at 1280px.
    for (const id of ["book-text-python", "book-text-fortran", "compare-python", "compare-fortran"]) {
      const clipped = await T(page, id).evaluate((el) => {
        const r = el.getBoundingClientRect();
        // either the element fits the viewport, or it scrolls (overflow auto/scroll)
        const ov = getComputedStyle(el).overflowX;
        const fits = r.right <= window.innerWidth + 1;
        const scrolls = el.scrollWidth <= el.clientWidth + 1 || ov === "auto" || ov === "scroll";
        return !(fits && scrolls);
      });
      expect(clipped, `${id} is clipped`).toBe(false);
    }
    // the last line of the fortran text is fully inside the viewport horizontally
    const box = await T(page, "compare-fortran").boundingBox();
    expect(box!.x + box!.width).toBeLessThanOrEqual(1281);
    const doc = await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1);
    expect(doc).toBe(true);
  });

  test("custom expression disables fortran/compare and runs on python", async ({ page }) => {
    await page.goto("/programs/ch01_p01");
    await page.locator("#custom-expr").fill("x**3 - x - 1");
    await page.locator("#in-x1").fill("1");
    await page.locator("#in-x2").fill("2");
    await expect(page.locator("#function-select")).toHaveValue(/custom/i);
    await expect(page.locator("#engine-fortran")).toBeDisabled();
    await expect(page.locator("#engine-compare")).toBeDisabled();
    await expect(T(page, "engine-custom-note")).toContainText("Python engine only");
    await run(page);
    await expect(T(page, "result-engine")).toContainText("python");
    await expect(T(page, "result-value")).toContainText("1.3247");
  });

  test("bad custom expression marks the field with a caret pointer", async ({ page }) => {
    await page.goto("/programs/ch01_p01");
    await page.locator("#custom-expr").fill("x**3 - 2*y");
    await run(page);
    await expect(T(page, "validation-error")).toHaveAttribute("data-code", "EXPRESSION");
    await expect(T(page, "validation-error")).toContainText("unknown name 'y'");
    await expect(T(page, "field-error-expression")).toBeVisible();
    await expect(page.getByText("Problem at column 10")).toBeVisible();
  });

  test("out-of-range input shows message and aria-invalid on the field", async ({ page }) => {
    await page.goto("/programs/ch01_p01");
    await page.locator("#in-x2").fill("5000");
    await run(page);
    await expect(T(page, "validation-error")).toContainText("Please correct the highlighted values.");
    await expect(T(page, "validation-error")).toContainText("5000.0 is above the maximum 1000.0");
    // Fix 55b6cd6: invalid inputs get aria-invalid.
    await expect(page.locator("#in-x2")).toHaveAttribute("aria-invalid", "true");
    await expect(page.locator("#in-x1")).not.toHaveAttribute("aria-invalid", "true");
  });

  test("reset restores the book card and clears the results panel", async ({ page }) => {
    await page.goto("/programs/ch01_p01");
    await page.locator("#in-x2").fill("5000");
    await run(page);
    await expect(T(page, "validation-error")).toBeVisible();
    await T(page, "reset-button").click();
    await expect(page.locator("#in-x2")).toHaveValue("1.0");
    await expect(page.locator("#custom-expr")).toHaveValue("");
    await expect(page.locator("#engine-python")).toBeChecked();
    // Fix 55b6cd6: reset clears stale results.
    await expect(T(page, "validation-error")).toHaveCount(0);
    await expect(T(page, "results-placeholder")).toBeVisible();
  });

  test("reset also clears a successful result", async ({ page }) => {
    await page.goto("/programs/ch01_p01");
    await run(page);
    await T(page, "reset-button").click();
    await expect(T(page, "results-body")).toHaveCount(0);
    await expect(T(page, "results-placeholder")).toBeVisible();
  });

  test("tabs show scan, legacy OCR, Fortran, Python and study content", async ({ page }) => {
    await page.goto("/programs/ch01_p01");
    await T(page, "tab-scan").click();
    await expect(T(page, "panel-scan")).toBeVisible();
    await expect(page.locator('object[data="/files/ch01_p01/scan"]')).toHaveCount(1);
    await expect(T(page, "scan-download")).toBeVisible();
    await T(page, "tab-legacy").click();
    await expect(T(page, "panel-legacy")).toBeVisible();
    await expect(T(page, "panel-legacy")).not.toBeEmpty();
    await T(page, "tab-fortran").click();
    await expect(T(page, "fortran-module-source")).toBeVisible();
    await expect(T(page, "fortran-app-source")).toBeAttached();
    await T(page, "tab-python").click();
    await expect(T(page, "python-source")).toBeVisible();
    await T(page, "tab-study").click();
    await expect(T(page, "study-content")).toContainText("Chapter 1, Program 1: Interval halving (bisection)");
  });

  test("practice question gives engine-checked feedback", async ({ page }) => {
    await page.goto("/programs/ch01_p01");
    await page.getByTestId("practice-answer-book-iterations").fill("15");
    await page.getByTestId("practice-submit-book-iterations").click();
    const fb = page.getByTestId("practice-feedback-book-iterations");
    await expect(fb.getByTestId("practice-verdict")).toHaveAttribute("data-correct", "true", { timeout: 15000 });
    await expect(fb).toContainText("Correct");
    await expect(fb.getByTestId("practice-computed-python")).toContainText("15");
    await expect(fb.getByTestId("practice-computed-fortran")).toContainText("15");

    await page.getByTestId("practice-answer-loose-tol-iterations").fill("3");
    await page.getByTestId("practice-submit-loose-tol-iterations").click();
    const fb2 = page.getByTestId("practice-feedback-loose-tol-iterations");
    await expect(fb2.getByTestId("practice-verdict")).toHaveAttribute("data-correct", "false", { timeout: 15000 });
    await expect(fb2).toContainText("The engine computes 9");
  });
});

test.describe("Bairstow", () => {
  test("book card gives the book factors in python and compare", async ({ page }) => {
    await page.goto("/programs/ch01_p02");
    await expect(page.locator("#in-a-2")).toHaveValue("-17.8");
    await expect(page.locator("#in-lim")).toHaveValue("20");
    await run(page);
    const text = T(page, "book-text");
    await expect(text).toContainText("X**2 +    4.19999 X +   -2.09999");
    await expect(text).toContainText("X**2 +    3.30000 X +   -6.20000");
    await expect(text).toContainText("1.00000X +  -10.30000");
    await expect(page.locator(".js-plotly-plot")).toHaveCount(5);
    await run(page, "compare");
    await expect(T(page, "compare-summary")).toContainText("agree");
    await expect(T(page, "compare-iterations")).toContainText("python 13, fortran 13");
  });
});

test.describe("Simpson", () => {
  test("book card gives 1.5499312 with 100 panels", async ({ page }) => {
    await page.goto("/programs/ch03_p01");
    await expect(page.locator("#in-b")).toHaveValue("5.0");
    await expect(page.locator("#in-n")).toHaveValue("100");
    await run(page);
    await expect(T(page, "result-value")).toContainText("1.54993123");
    await expect(T(page, "book-text")).toContainText("VALUE OF SINE INTEGRAL FROM X = 0 TO X =  5.00 IS 1.5499312 WITH 100 PANELS");
    await expect(T(page, "chart-integrand_panels")).toBeVisible();
    await run(page, "compare");
    await expect(T(page, "compare-summary")).toContainText("agree");
  });

  test("custom x**2 integrates to 9 and odd panels are rejected", async ({ page }) => {
    await page.goto("/programs/ch03_p01");
    await page.locator("#custom-expr").fill("x**2");
    await page.locator("#in-b").fill("3");
    await page.locator("#in-n").fill("10");
    await expect(page.locator("#engine-fortran")).toBeDisabled();
    await run(page);
    const v = parseFloat((await T(page, "result-value").textContent()) ?? "");
    expect(Math.abs(v - 9)).toBeLessThan(1e-9);
    await page.locator("#in-n").fill("7");
    await run(page);
    await expect(page.getByText("ODD NUMBER OF PANELS").first()).toBeVisible();
  });

  test("preset 2 and fortran-only run work", async ({ page }) => {
    await page.goto("/programs/ch03_p01");
    await page.locator("#function-select").selectOption({ index: 1 });
    await run(page, "fortran");
    await expect(T(page, "result-engine")).toContainText("fortran");
    await expect(T(page, "result-value")).toBeVisible();
  });
});

test.describe("Romberg", () => {
  test("book card gives 1.6181944 with 80 subintervals", async ({ page }) => {
    await page.goto("/programs/ch03_p02");
    await expect(page.locator("#in-b")).toHaveValue("15.0");
    await expect(page.locator("#in-tol")).toHaveValue("2e-07");
    await run(page);
    await expect(T(page, "result-value")).toContainText("1.61819444");
    await expect(T(page, "book-text")).toContainText("VALUE IS  1.6181944");
    await expect(T(page, "book-text")).toContainText("80 SUBINTERVALS WERE REQUIRED");
    await expect(T(page, "chart-romberg_heatmap")).toBeVisible();
    await run(page, "compare");
    await expect(T(page, "compare-summary")).toContainText("agree");
  });
});

test.describe("Lagrange interpolation", () => {
  test("book card interpolates 2.3119 at XIN=5", async ({ page }) => {
    await page.goto("/programs/lagrange_interpolation");
    await expect(page.locator("#in-n")).toHaveValue("5");
    await expect(page.locator("#in-xin")).toHaveValue("5.0");
    await expect(page.locator("#in-points-0-x")).toHaveValue("2.3756");
    await run(page);
    await expect(T(page, "result-value")).toContainText("2.31190129");
    await expect(T(page, "chart-interpolant")).toBeVisible();
    await run(page, "compare");
    await expect(T(page, "compare-summary")).toContainText("agree");
  });

  test("add/remove point rows keep N in sync; blank row is a validation error", async ({ page }) => {
    await page.goto("/programs/lagrange_interpolation");
    await T(page, "add-row-points").click();
    await expect(page.locator("#in-n")).toHaveValue("6");
    await run(page);
    await expect(T(page, "validation-error")).toContainText("a value is required");
    await T(page, "remove-row-points-5").click();
    await expect(page.locator("#in-n")).toHaveValue("5");
  });

  test("bad XIN is reported and reset restores 5 rows", async ({ page }) => {
    await page.goto("/programs/lagrange_interpolation");
    await page.locator("#in-xin").fill("abc");
    await run(page);
    await expect(T(page, "validation-error")).toContainText("'abc' is not a number");
    await expect(page.locator("#in-xin")).toHaveAttribute("aria-invalid", "true");
    await T(page, "add-row-points").click();
    await T(page, "reset-button").click();
    await expect(page.locator("#in-xin")).toHaveValue("5.0");
    await expect(page.locator("#in-n")).toHaveValue("5");
    await expect(page.locator('input[id^="in-points-"][id$="-x"]')).toHaveCount(5);
    await expect(T(page, "results-placeholder")).toBeVisible();
  });

  test("scan tab says no scan is available", async ({ page }) => {
    await page.goto("/programs/lagrange_interpolation");
    await T(page, "tab-scan").click();
    await expect(T(page, "panel-scan")).toContainText("No scan available for this program");
    await expect(T(page, "panel-scan")).toContainText("unconfirmed");
  });
});
