import { test, expect } from "@playwright/test";
import { T, run } from "./helpers";

// Labels quoted by README.md "Using the web interface" must match the app.
const P1 = "/programs/ch01_p01";

test.describe("README step 1: choose a program", () => {
  test("home groups by chapter, unconfirmed last", async ({ page }) => {
    await page.goto("/");
    for (const h of ["Chapter 1: Solution of Nonlinear Equations", "Chapter 3: Numerical Integration", "Chapter 4: Numerical Differentiation"])
      await expect(page.getByRole("heading", { name: h })).toBeVisible();
    const unconf = T(page, "chapter-unconfirmed");
    await expect(unconf.locator("h2")).toHaveText("Book reference unconfirmed");
    await expect(unconf).toContainText("unconfirmed");
    await expect(unconf).toContainText("No scan");
    await expect(unconf).toContainText("Engines: python, fortran, compare");
    await expect(page.getByText("Scan available").first()).toBeVisible();
    await expect(page.getByRole("link", { name: "JSON API" })).toBeVisible();
    await expect(page.getByRole("link", { name: "API docs" })).toBeVisible();
  });
});

test.describe("README step 2: run form", () => {
  test("help, bounds, data card toggle, presets", async ({ page }) => {
    await page.goto(P1);
    await expect(T(page, "input-x1")).toHaveValue("0.0");
    await expect(T(page, "input-tol")).toHaveValue("1e-05");
    await expect(T(page, "field-help-x1")).toContainText("Left end of the starting interval");
    await expect(T(page, "field-bounds-x1")).toContainText("min -1000.0, max 1000.0");
    await page.getByText("Book data card", { exact: true }).click();
    await expect(page.locator("details", { hasText: "Book data card" }).first().getByText("0.        1.        1.E-5")).toBeVisible();
    await expect(T(page, "preset-select").locator("option")).toHaveText([
      "1: Book: exp(-x) - sin(pi x / 2)", "2: x^3 - x - 1", "3: cos(x) - x", "Custom expression (Python engine only)",
    ]);
    await expect(T(page, "preset-expr")).toContainText("Preset F(x) = EXP(-X) - SIN(3.1415926*X/2.)");
  });

  test("invalid input shows INPUT and per-field lines", async ({ page }) => {
    await page.goto(P1);
    await T(page, "input-x1").fill("abc");
    await T(page, "input-tol").fill("5");
    await T(page, "run-button").click();
    const err = T(page, "validation-error");
    await expect(err).toBeVisible();
    await expect(err).toContainText("INPUT");
    await expect(err).toContainText("Please correct the highlighted values.");
    await expect(err).toContainText("X1: 'abc' is not a number (examples: 0.5, 1.E-5)");
    await expect(err).toContainText("TOL: 5.0 is above the maximum 1.0");
  });

  test("Reset to book data card restores values and clears results", async ({ page }) => {
    await page.goto(P1);
    await run(page, "python");
    await T(page, "input-x1").fill("0.25");
    await expect(T(page, "reset-button")).toHaveText("Reset to book data card");
    await T(page, "reset-button").click();
    await expect(T(page, "input-x1")).toHaveValue("0.0");
    await expect(T(page, "input-tol")).toHaveValue("1e-05");
    await expect(T(page, "results-body")).toHaveCount(0);
  });

  test("Bairstow has seven A fields and no list buttons", async ({ page }) => {
    await page.goto("/programs/ch01_p02");
    await expect(page.locator("[data-testid^='input-a-']")).toHaveCount(7);
    await expect(page.getByRole("button", { name: /Add (point|entry)|Remove/ })).toHaveCount(0);
    await expect(T(page, "preset-select")).toHaveCount(0);
  });

  test("Lagrange Add point / Remove keep N in sync", async ({ page }) => {
    await page.goto("/programs/lagrange_interpolation");
    await expect(page.getByText("Updated automatically when you add or remove a row")).toBeVisible();
    await expect(page.getByRole("button", { name: "Remove" })).toHaveCount(5);
    await page.getByRole("button", { name: "Add point" }).click();
    await expect(page.getByRole("button", { name: "Remove" })).toHaveCount(6);
    await expect(page.locator("[data-testid='input-n']")).toHaveValue("6");
    await page.getByRole("button", { name: "Remove" }).last().click();
    await expect(page.locator("[data-testid='input-n']")).toHaveValue("5");
  });
});

test.describe("README step 3: custom function", () => {
  const cases: [string, number | null, string][] = [
    ["x**", 3, "Problem at column 3"],
    ["sin(x", 4, "Problem at column 4"],
    ["foo(x)", 1, "Problem at column 1"],
    ["x + y", 5, "Problem at column 5"],
  ];
  for (const [expr, col, text] of cases) {
    test(`expression error ${expr}`, async ({ page }) => {
      await page.goto(P1);
      await T(page, "custom-expr").fill(expr);
      await T(page, "run-button").click();
      await expect(T(page, "validation-error")).toBeVisible();
      await expect(T(page, "validation-error")).toContainText("EXPRESSION");
      await expect(T(page, "validation-error")).toContainText(text);
    });
  }

  test("domain error and engines disabled while custom", async ({ page }) => {
    await page.goto(P1);
    await T(page, "custom-expr").fill("log(x - 2)");
    await expect(T(page, "engine-fortran")).toBeDisabled();
    await expect(T(page, "engine-compare")).toBeDisabled();
    await expect(T(page, "engine-custom-note")).toBeVisible();
    await run(page);
    await expect(T(page, "results-body").or(T(page, "validation-error")).first()).toContainText("outside the function's domain");
    await expect(T(page, "results-body").or(T(page, "validation-error")).first()).toContainText("EXPRESSION");
  });

  test("function name aliases accepted", async ({ page }) => {
    await page.goto(P1);
    await T(page, "custom-expr").fill("EXPF(-X) - SINF(3.1415926*X/2.)");
    await run(page);
    await expect(T(page, "results-body")).toContainText("15");
  });
});

test.describe("README steps 4-5: engines and results", () => {
  test("python run shows result, chart, book output, details", async ({ page }) => {
    await page.goto(P1);
    await run(page, "python");
    const body = T(page, "results-body");
    await expect(body).toContainText("0.443572998046875");
    await expect(body).toContainText(/CONVERGED/i);
    await expect(body).toContainText("Iterations (15 rows, python engine)");
    await expect(body).toContainText("Result details");
    await expect(body).toContainText("Book-format output (python)");
    await expect(body.locator(".js-plotly-plot").first()).toBeVisible();
  });

  test("compare view", async ({ page }) => {
    await page.goto(P1);
    test.skip(!(await T(page, "engine-compare").isEnabled()), "compare unavailable");
    await run(page, "compare");
    const body = T(page, "results-body");
    await expect(body).toContainText("The engines agree bit for bit");
    await expect(body).toContainText("Iterations: python 15, fortran 15");
    await expect(body).toContainText("Outcome: python OK, fortran OK");
    await expect(body).toContainText("Per column");
  });

  test("bisection BRACKET error result", async ({ page }) => {
    await page.goto(P1);
    await T(page, "input-x1").fill("0.5");
    await run(page, "python");
    const body = T(page, "results-body");
    await expect(body).toContainText("BRACKET");
    await expect(body).toContainText("NOT OF OPPOSITE SIGNS");
    await expect(body).toContainText("python engine.");
    await expect(body).toContainText("No iteration rows.");
  });

  test("Bairstow NON_CONVERGENT with LIM=4", async ({ page }) => {
    await page.goto("/programs/ch01_p02");
    await page.locator("[data-testid='input-lim']").first().fill("4");
    await run(page, "python");
    const body = T(page, "results-body");
    await expect(body).toContainText("NON_CONVERGENT");
    await expect(body).toContainText("DOES NOT CONVERGE AFTER 4 ITERATIONS");
    await expect(body).toContainText("the 4 iteration rows computed before the error are shown below");
  });
});

test.describe("README steps 6-7: sources and practice", () => {
  test("source tabs and download links", async ({ page }) => {
    await page.goto(P1);
    for (const k of ["scan", "legacy", "fortran", "python", "study"]) await expect(T(page, `tab-${k}`)).toBeVisible();
    await expect(page.getByRole("tab", { name: "Original scan" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Legacy OCR text" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Modern Fortran" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Study page" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Open the scan (PDF) in a new tab" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Download the scan" })).toBeVisible();
    await T(page, "tab-python").click();
    await expect(page.getByRole("link", { name: "raw file" }).first()).toHaveAttribute("href", /\/files\/ch01_p01\/python/);
    await T(page, "tab-study").click();
    await expect(page.getByRole("link", { name: "Markdown source" })).toHaveAttribute("href", /\/files\/ch01_p01\/study/);
  });

  test("Lagrange has no scan", async ({ page }) => {
    await page.goto("/programs/lagrange_interpolation");
    await T(page, "tab-scan").click();
    await expect(page.getByText("No scan available for this program")).toBeVisible();
  });

  test("practice feedback correct, incorrect, invalid", async ({ page }) => {
    await page.goto(P1);
    const ans = page.locator("[data-testid^='practice-answer-']");
    const submit = page.locator("[data-testid^='practice-submit-']");
    const fb = page.locator("[data-testid^='practice-feedback-']");
    await ans.first().fill("15");
    await submit.first().click();
    await expect(fb.first()).toContainText("Correct");
    await expect(fb.first()).toContainText("Your answer matches the computed 15.");
    await ans.first().fill("abc");
    await submit.first().click();
    await expect(fb.first()).toContainText("'abc' is not a number (examples: 0.5, 1.E-5)");
  });
});
