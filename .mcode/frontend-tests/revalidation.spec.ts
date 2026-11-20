import { test, expect } from "@playwright/test";
import { T, run } from "./helpers";

test.describe("Re-validation extras", () => {
  test("bisection python result is 0.4435729 / 15 iterations with charts", async ({ page }) => {
    await page.goto("/programs/ch01_p01");
    await run(page);
    await expect(T(page, "result-iterations")).toContainText("15");
    await expect(T(page, "book-text")).toContainText("THE VALUE, X =   .4435729 IS A ROOT.  15 ITERATIONS WERE REQUIRED.");
    await expect(page.locator(".js-plotly-plot")).toHaveCount(2);
    await expect(T(page, "step-row")).toHaveCount(15);
  });

  test("romberg on the fortran engine gives 80 subintervals", async ({ page }) => {
    await page.goto("/programs/ch03_p02");
    await run(page, "fortran");
    await expect(T(page, "result-engine")).toContainText("fortran");
    await expect(T(page, "book-text")).toContainText("80 SUBINTERVALS WERE REQUIRED TO MEET TOLERANCE OF  2.0000000E-07");
  });

  for (const id of ["ch01_p01", "ch01_p02", "ch03_p01", "ch03_p02", "lagrange_interpolation"]) {
    test(`compare mode agrees bit for bit on ${id}`, async ({ page }) => {
      await page.goto(`/programs/${id}`);
      await run(page, "compare");
      await expect(T(page, "compare-view")).toBeVisible();
      await expect(T(page, "compare-verdict")).toContainText("agree");
      await expect(T(page, "diff-cell")).toHaveCount(0);
    });
  }

  test("unsafe custom expression is rejected with a column", async ({ page }) => {
    await page.goto("/programs/ch01_p01");
    await page.locator("#custom-expr").fill("__import__('os').system('id')");
    await run(page);
    await expect(T(page, "validation-error")).toContainText("attribute access");
    await expect(T(page, "field-error-expression")).toBeVisible();
    await expect(T(page, "expr-error-column")).toContainText("1");
  });

  test("syntax error in custom expression is reported", async ({ page }) => {
    await page.goto("/programs/ch01_p01");
    await page.locator("#custom-expr").fill("x +");
    await run(page);
    await expect(T(page, "validation-error")).toContainText("syntax error");
    await expect(T(page, "expr-error-column")).toContainText("3");
  });

  test("non-bracketing interval reports the book error", async ({ page }) => {
    await page.goto("/programs/ch01_p01");
    await page.locator("#in-x1").fill("2");
    await page.locator("#in-x2").fill("3");
    await run(page);
    await expect(T(page, "results").getByText("BRACKET FUNCTION VALUES WITH INITIAL X VALUES ARE NOT OF OPPOSITE SIGNS. CHANGE INPUTS.").first()).toBeVisible();
  });

  test("multiple field errors are shown together", async ({ page }) => {
    await page.goto("/programs/ch01_p01");
    await page.locator("#in-x1").fill("5000");
    await page.locator("#in-tol").fill("abc");
    await run(page);
    await expect(T(page, "field-error-x1")).toContainText("above the maximum");
    await expect(T(page, "field-error-tol")).toContainText("is not a number");
    await expect(page.locator("#in-x1")).toHaveAttribute("aria-invalid", "true");
    await expect(page.locator("#in-tol")).toHaveAttribute("aria-invalid", "true");
  });

  test("practice: non-numeric answer gets a parse message, wrong answer incorrect", async ({ page }) => {
    await page.goto("/programs/ch01_p01");
    await T(page, "practice-answer-book-iterations").fill("abc");
    await T(page, "practice-submit-book-iterations").click();
    await expect(T(page, "practice-feedback-book-iterations")).toContainText("is not a number", { timeout: 15000 });
    await T(page, "practice-answer-book-iterations").fill("99");
    await T(page, "practice-submit-book-iterations").click();
    await expect(T(page, "practice-feedback-book-iterations").getByTestId("practice-verdict")).toHaveAttribute("data-correct", "false", { timeout: 15000 });
  });

  test("scan tab embeds the PDF and serves it", async ({ page, request }) => {
    await page.goto("/programs/ch01_p01");
    await T(page, "tab-scan").click();
    await expect(T(page, "scan-viewer")).toHaveAttribute("data", "/files/ch01_p01/scan");
    const r = await request.get("/files/ch01_p01/scan");
    expect(r.status()).toBe(200);
    expect(r.headers()["content-type"]).toContain("pdf");
  });
});
