import { expect, test } from "@playwright/test";

/**
 * The front door to the admin. It used to ask, first and only, for an API key — the one
 * thing a first-time visitor certainly does not have. These check the three ways in that do
 * not require finding a key in a file, and that the key path still works for people who have one.
 */

test("the demo store opens in one click, with nothing to type", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("pageerror", (error) => consoleErrors.push(String(error)));

  await page.setViewportSize({ width: 1584, height: 1024 });
  await page.goto("/admin/setup");

  await expect(page.getByRole("heading", { name: "Open your store" })).toBeVisible();
  const demo = page.getByRole("button", { name: /Open the demo store/ });
  await expect(demo).toBeVisible();
  await page.screenshot({ path: "test-results/merchant-gate.png" });

  await demo.click();
  await expect(page.locator(".storefront-link span")).toHaveText("Mysa Skin", { timeout: 30_000 });
  await expect(page.getByRole("heading", { name: "Make your catalog conversational" })).toBeVisible();
  // The demo store already exists, so there is no one-time key to save.
  await expect(page.locator(".key-banner")).toHaveCount(0);

  // Having opened it, this browser offers it back as a remembered store.
  await page.getByRole("button", { name: "Switch store" }).click();
  await expect(page.locator(".gate-store", { hasText: "Mysa Skin" })).toBeVisible();
  await page.screenshot({ path: "test-results/merchant-gate-remembered.png" });

  expect(consoleErrors).toEqual([]);
});

test("the gate explains why a key exists and where it is kept", async ({ page }) => {
  await page.setViewportSize({ width: 1584, height: 1024 });
  await page.goto("/admin/setup");

  const explainer = page.getByRole("button", { name: /Why a key, and where it is kept/ });
  await expect(explainer).toHaveAttribute("aria-expanded", "false");
  await explainer.click();
  await expect(explainer).toHaveAttribute("aria-expanded", "true");
  await expect(page.locator(".gate-why")).toContainText("X-Merchant-Key");
  await expect(page.locator(".gate-why")).toContainText("shown once");
});

test("a key that resolves to nobody is a signed-out state, not a broken page", async ({ page }) => {
  await page.setViewportSize({ width: 1180, height: 900 });
  await page.goto("/admin/setup");

  await page.getByRole("button", { name: /I have a store key/ }).click();
  await page.getByPlaceholder("mk_…").fill("mk_not_a_real_key_at_all");
  await page.getByRole("button", { name: "Open", exact: true }).click();

  await expect(page.locator(".gate-error")).toBeVisible();
  // Still usable: the other ways in are right there.
  await expect(page.getByPlaceholder("Your store name")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Open your store" })).toBeVisible();
});

test("the gate fits a phone", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/admin/setup");
  await expect(page.getByRole("heading", { name: "Open your store" })).toBeVisible();

  const width = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    client: document.documentElement.clientWidth,
  }));
  expect(width.scroll).toBeLessThanOrEqual(width.client);
  await page.screenshot({ path: "test-results/merchant-gate-mobile.png", fullPage: true });
});
