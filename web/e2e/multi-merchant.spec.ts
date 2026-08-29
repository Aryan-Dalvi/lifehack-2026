import { expect, test } from "@playwright/test";

test("a brand new merchant can sign up and gets their own store", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (m) => m.type() === "error" && consoleErrors.push(m.text()));
  page.on("pageerror", (e) => consoleErrors.push(String(e)));

  await page.setViewportSize({ width: 1584, height: 1024 });
  await page.goto("/admin");

  // Signed out: both a sign-in and a sign-up path are offered.
  await expect(page.getByRole("heading", { name: "Merchant sign in" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "New here?" })).toBeVisible();
  await page.screenshot({ path: "test-results/mm-1-gate.png" });

  const storeName = `Aurora Skin ${Date.now().toString().slice(-5)}`;
  await page.getByPlaceholder("Your store name").fill(storeName);
  await page.getByRole("button", { name: "Create my store" }).click();

  // The key is shown once, before anything else.
  await expect(page.getByRole("heading", { name: "Your store is ready" })).toBeVisible({ timeout: 30_000 });
  const key = (await page.locator(".new-store-key").innerText()).trim();
  const merchantId = (await page.locator(".new-store-id code").innerText()).trim();
  console.log(`  created ${merchantId} with key ${key.slice(0, 6)}…`);
  expect(key).toMatch(/^mk_/);
  expect(merchantId).toMatch(/^m_/);
  await page.screenshot({ path: "test-results/mm-2-key.png" });

  await page.getByRole("button", { name: /I have saved it/ }).click();

  // The dashboard is THIS store, not the seeded demo store.
  await expect(page.locator(".storefront-link span")).toHaveText(storeName, { timeout: 30_000 });
  const hosted = await page.locator(".storefront-link").getAttribute("href");
  console.log("  storefront:", hosted);
  expect(hosted).toContain(merchantId);
  expect(hosted).not.toContain("m_mysa");

  const snippet = await page.locator("code").filter({ hasText: "widget.js" }).first().innerText();
  expect(snippet).toContain(merchantId);
  expect(snippet).not.toContain("m_mysa");

  // A brand new store has no catalog of its own - it must not show Mysa's.
  const previewNames = await page.locator(".preview-products article strong").allInnerTexts();
  console.log("  preview products:", JSON.stringify(previewNames));
  expect(previewNames).toEqual([]);
  await page.screenshot({ path: "test-results/mm-3-dashboard.png" });

  // Switching store returns to the gate, and the key no longer opens the dashboard.
  await page.getByRole("button", { name: "Switch store" }).click();
  await expect(page.getByRole("heading", { name: "Merchant sign in" })).toBeVisible();

  // Signing back in with the saved key reopens the same store.
  await page.getByPlaceholder("mk_…").fill(key);
  await page.getByRole("button", { name: "Open store setup" }).click();
  await expect(page.locator(".storefront-link span")).toHaveText(storeName, { timeout: 30_000 });
  console.log("  signed back in to", storeName);

  expect(consoleErrors).toEqual([]);
});
