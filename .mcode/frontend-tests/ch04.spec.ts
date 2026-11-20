import { test, expect } from "@playwright/test";
import { T, run } from "./helpers";

const URL = "/programs/ch04_p01";

test.describe("Home chapter 4", () => {
  test("Chapter 4 group links to ch04_p01", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Chapter 4: Numerical Differentiation" })).toBeVisible();
    await page.getByRole("link", { name: "Derivatives by central differences" }).click();
    await expect(page).toHaveURL(/\/programs\/ch04_p01$/);
  });
});

test.describe("ch04_p01 form", () => {
  test("page header and book data card defaults", async ({ page }) => {
    await page.goto(URL);
    await expect(T(page, "program-title")).toHaveText("Derivatives by central differences");
    await expect(T(page, "book-ref")).toContainText("Chapter 4, Program 1, page 90");
    await expect(T(page, "program-id")).toHaveText("ch04_p01");
    await expect(T(page, "input-x")).toHaveValue("0.0");
    await expect(T(page, "input-h")).toHaveValue("0.1");
    await expect(T(page, "engine-python")).toBeChecked();
    await expect(T(page, "preset-expr")).toContainText("X**2*EXP(X)");
    await expect(T(page, "results-placeholder")).toBeVisible();
    await expect(T(page, "preset-select").locator("option")).toHaveText([
      "1: Book: x^2 e^x", "2: sin(x)", "3: 1 + log10(x) (p. 91, problem 2)", "Custom expression (Python engine only)",
    ]);
  });

  test("reset restores the book data card", async ({ page }) => {
    await page.goto(URL);
    await T(page, "input-x").fill("2");
    await T(page, "input-h").fill("0.5");
    await run(page);
    await T(page, "reset-button").click();
    await expect(T(page, "input-x")).toHaveValue("0.0");
    await expect(T(page, "input-h")).toHaveValue("0.1");
    await expect(T(page, "results-placeholder")).toBeVisible();
  });
});

test.describe("ch04_p01 runs", () => {
  test("python book card gives 10-row table, charts, book text", async ({ page }) => {
    await page.goto(URL);
    await run(page);
    await expect(T(page, "step-row")).toHaveCount(10);
    await expect(T(page, "step-row").first()).toContainText("1.0016675E-02");
    await expect(T(page, "step-row").first()).toContainText("2.0100083E+00");
    await expect(T(page, "step-row").last()).toContainText("1.0000000E-20");
    await expect(T(page, "step-row").last()).toContainText("2.0000000E+00");
    await expect(T(page, "result-value")).toContainText("1.0000000031710762e-20");
    await expect(T(page, "extra-first_dx")).toContainText("0.010016675001984412");
    await expect(T(page, "extra-last_ddx")).toContainText("2.0");
    await expect(T(page, "book-text")).toContainText("DERIVATIVES COMPUTED BY CENTRAL DIFFERENCE FORMULAS");
    await expect(T(page, "book-text")).toContainText("AT X =  0.00");
    for (const c of ["convergence_dx", "convergence_ddx", "convergence_changes"]) {
      await expect(T(page, `chart-${c}`)).toBeVisible();
    }
    await expect(page.locator(".js-plotly-plot").first()).toBeVisible();
  });

  test("fortran engine matches", async ({ page }) => {
    await page.goto(URL);
    await run(page, "fortran");
    await expect(T(page, "result-engine")).toContainText("fortran");
    await expect(T(page, "step-row")).toHaveCount(10);
    await expect(T(page, "result-value")).toContainText("1.0000000031710762e-20");
  });

  test("compare engines agree bit for bit", async ({ page }) => {
    await page.goto(URL);
    await run(page, "compare");
    await expect(T(page, "compare-view")).toBeVisible();
    await expect(T(page, "compare-verdict")).toContainText("agree bit for bit");
    await expect(T(page, "compare-iterations")).toContainText("python 10, fortran 10");
    await expect(T(page, "step-row")).toHaveCount(20);
    await expect(T(page, "diff-cell")).toHaveCount(0);
    await expect(T(page, "book-text-python")).toBeVisible();
    await expect(T(page, "book-text-fortran")).toBeVisible();
  });

  test("preset 2 sin(x)", async ({ page }) => {
    await page.goto(URL);
    await T(page, "preset-select").selectOption("2");
    await run(page);
    await expect(T(page, "step-row").first()).toContainText("9.9833417E-01");
    await expect(T(page, "step-row").first()).toContainText("0.0000000E+00");
  });

  test("preset 3 log10 with X=0.19 H=0.02", async ({ page }) => {
    await page.goto(URL);
    await T(page, "preset-select").selectOption("3");
    await T(page, "input-x").fill("0.19");
    await T(page, "input-h").fill("0.02");
    await run(page);
    await expect(T(page, "step-row").first()).toContainText("2.2942593E+00");
    await expect(T(page, "step-row").first()).toContainText("-1.2097464E+01");
  });

  test("preset 3 at X=0 shows domain error", async ({ page }) => {
    await page.goto(URL);
    await T(page, "preset-select").selectOption("3");
    await run(page);
    await expect(page.locator("#results")).toContainText("outside the function's domain");
  });

  test("custom SIN(X) at X=1", async ({ page }) => {
    await page.goto(URL);
    await T(page, "custom-expr").fill("SIN(X)");
    await T(page, "input-x").fill("1");
    await run(page);
    await expect(T(page, "result-value")).toContainText("0.540302247387103");
    await expect(T(page, "extra-first_dx")).toContainText("0.53940225216976");
  });
});

test.describe("ch04_p01 validation", () => {
  test("syntax error in custom expression reports column", async ({ page }) => {
    await page.goto(URL);
    await T(page, "custom-expr").fill("SIN(X");
    await run(page);
    await expect(T(page, "validation-error")).toContainText("'(' was never closed");
    await expect(T(page, "field-error-expression")).toBeVisible();
    await expect(T(page, "expr-error-column")).toContainText("4");
    await expect(T(page, "expr-error-position")).toBeVisible();
  });

  test("H above maximum", async ({ page }) => {
    await page.goto(URL);
    await T(page, "input-h").fill("50");
    await run(page);
    await expect(T(page, "validation-error")).toContainText("H: 50.0 is above the maximum 10.0");
  });

  test("H not a number", async ({ page }) => {
    await page.goto(URL);
    await T(page, "input-h").fill("abc");
    await run(page);
    await expect(T(page, "validation-error")).toContainText("H: 'abc' is not a number");
  });
});

test.describe("ch04_p01 tabs", () => {
  test("scan tab", async ({ page }) => {
    await page.goto(URL);
    await T(page, "tab-scan").click();
    await expect(T(page, "scan-download")).toBeVisible();
    const r = await page.request.get("/files/ch04_p01/scan");
    expect(r.status()).toBe(200);
    expect(r.headers()["content-type"]).toContain("pdf");
  });

  test("legacy tab shows PDF links", async ({ page }) => {
    await page.goto(URL);
    await T(page, "tab-legacy").click();
    for (const [i, href] of [[0, "/files/ch04_p01/legacy"], [1, "/files/ch04_p01/legacy?index=1"]] as const) {
      const entry = T(page, `legacy-source-${i}-pdf`);
      await expect(entry).toContainText("no OCR text");
      const a = entry.locator("a");
      await expect(a).toHaveAttribute("href", href);
      const r = await page.request.get(href);
      expect(r.status()).toBe(200);
      expect(r.headers()["content-type"]).toContain("pdf");
      await expect(T(page, `download-legacy-source-${i}`)).toBeVisible();
    }
  });

  test("fortran, python and study tabs", async ({ page }) => {
    await page.goto(URL);
    await T(page, "tab-fortran").click();
    await expect(T(page, "fortran-module-source")).toContainText("derivative");
    await expect(T(page, "fortran-app-source")).toBeVisible();
    await T(page, "tab-python").click();
    await expect(T(page, "python-source")).toContainText("def ");
    await T(page, "tab-study").click();
    await expect(T(page, "study-content")).toContainText("Chapter 4, Program 1: Derivatives by central differences");
  });
});

test.describe("ch04_p01 practice", () => {
  const cases: [string, string, RegExp][] = [
    ["book-first-dx", "1.0016675E-02", /Correct/],
    ["rows", "10", /Correct/],
    ["book-last-ddx", "2.0", /Correct/],
    ["sin-second-derivative", "-0.8407700", /Correct/],
    ["book-first-dx", "5", /Incorrect/],
    ["rows", "7", /Incorrect/],
    ["log-table-derivative", "2.28576043", /Incorrect/],
    ["log-smallest-h", "2.2857604", /Incorrect/],
  ];
  for (const [id, ans, re] of cases) {
    test(`practice ${id} answer ${ans}`, async ({ page }) => {
      await page.goto(URL);
      await T(page, `practice-answer-${id}`).fill(ans);
      await T(page, `practice-submit-${id}`).click();
      await expect(T(page, `practice-feedback-${id}`)).toContainText(re);
    });
  }
});

test.describe("regression smoke", () => {
  test("ch03_p01 python run still works", async ({ page }) => {
    await page.goto("/programs/ch03_p01");
    await run(page);
    await expect(T(page, "result-value")).toContainText("1.5499312397703537");
    await expect(T(page, "step-row")).toHaveCount(101);
    await expect(T(page, "book-text")).toBeVisible();
  });

  for (const id of ["ch01_p01", "ch01_p02", "ch03_p02", "lagrange_interpolation"]) {
    test(`${id} page loads and runs`, async ({ page }) => {
      await page.goto(`/programs/${id}`);
      await expect(T(page, "run-button")).toBeVisible();
      await run(page);
      await expect(T(page, "book-text")).toBeVisible();
    });
  }
});
