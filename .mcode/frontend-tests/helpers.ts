import { expect, Page } from "@playwright/test";

export const T = (page: Page, id: string) => page.getByTestId(id);

export async function run(page: Page, engine?: "python" | "fortran" | "compare") {
  if (engine) await page.locator(`#engine-${engine}`).check();
  await T(page, "run-button").click();
  await expect(T(page, "results-body").or(T(page, "validation-error")).first()).toBeVisible({ timeout: 20000 });
}
