import { expect, test } from "@playwright/test";

/**
 * A merchant's storefront should carry their own mark. Before this, every store that
 * onboarded wore the seeded demo shop's name in the top left, which is the first thing a
 * real merchant would notice and the last thing they would forgive.
 */

// A 1x1 PNG, small enough to inline and real enough to pass the byte-signature check.
const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
  "base64",
);

test("a merchant uploads a logo and their storefront wears it", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("pageerror", (error) => consoleErrors.push(String(error)));

  await page.setViewportSize({ width: 1584, height: 1024 });
  await page.goto("/admin");

  const storeName = `Aurora Logo ${Date.now().toString().slice(-5)}`;
  await page.getByPlaceholder("Your store name").fill(storeName);
  await page.getByRole("button", { name: "Create my store" }).click();
  await expect(page.getByRole("heading", { name: "Your store is ready" })).toBeVisible({ timeout: 30_000 });
  const merchantId = (await page.locator(".new-store-id code").innerText()).trim();
  await page.getByRole("button", { name: /I have saved it/ }).click();
  await expect(page.locator(".storefront-link span")).toHaveText(storeName, { timeout: 30_000 });

  // Step 1 of onboarding is where a merchant sets their brand, so the logo lives there.
  const control = page.locator(".logo-control");
  await expect(control).toBeVisible();
  await expect(control.locator(".logo-preview--empty")).toBeVisible();
  await control.locator("input[type=file]").setInputFiles({
    name: "aurora.png",
    mimeType: "image/png",
    buffer: PNG,
  });

  // It appears in the control and in the live preview of the storefront beside it.
  await expect(control.locator("img")).toBeVisible();
  await expect(page.locator(".preview-logo")).toBeVisible();
  await expect(page.getByRole("button", { name: "Remove" })).toBeVisible();
  await page.screenshot({ path: "test-results/merchant-logo-setup.png" });

  // And on the storefront itself, in place of the store name.
  await page.goto(`/storefront?merchant=${merchantId}`);
  const mark = page.locator(".shopper-header .brand-logo");
  await expect(mark).toBeVisible();
  await expect(mark).toHaveAttribute("alt", storeName);
  await expect(page.locator(".shopper-header .brand span")).toHaveCount(0);
  await page.screenshot({ path: "test-results/merchant-logo-storefront.png" });

  expect(consoleErrors).toEqual([]);
});

test("the seeded storefront still shows its name when no logo is set", async ({ page }) => {
  await page.setViewportSize({ width: 1180, height: 820 });
  await page.goto("/storefront?merchant=m_mysa");
  await expect(page.locator(".shopper-header .brand span")).toHaveText("Mysa Skin");
  await expect(page.locator(".shopper-header .brand-logo")).toHaveCount(0);
});
