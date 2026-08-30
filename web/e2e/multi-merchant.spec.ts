import { expect, test } from "@playwright/test";

test("a brand new merchant can sign up and gets their own store", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (m) => m.type() === "error" && consoleErrors.push(m.text()));
  page.on("pageerror", (e) => consoleErrors.push(String(e)));

  await page.setViewportSize({ width: 1584, height: 1024 });
  await page.goto("/admin");

  // Signed out: creating a store is the front door, and the key is folded away behind it.
  await expect(page.getByRole("heading", { name: "Open your store" })).toBeVisible();
  await expect(page.getByPlaceholder("Your store name")).toBeVisible();
  await expect(page.getByPlaceholder("mk_…")).toHaveCount(0);
  await page.getByRole("button", { name: /I have a store key/ }).click();
  await expect(page.getByPlaceholder("mk_…")).toBeVisible();
  await page.screenshot({ path: "test-results/mm-1-gate.png" });

  const storeName = `Aurora Skin ${Date.now().toString().slice(-5)}`;
  await page.getByPlaceholder("Your store name").fill(storeName);
  await page.getByRole("button", { name: "Create my store" }).click();

  // Creating a store signs you in. The key is carried into the page rather than blocking it,
  // because it is shown exactly once and this is still the only copy.
  await expect(page.locator(".storefront-link span")).toHaveText(storeName, { timeout: 30_000 });
  const key = (await page.locator(".key-banner code").innerText()).trim();
  expect(key).toMatch(/^mk_/);
  await page.screenshot({ path: "test-results/mm-2-key.png" });

  // The dashboard is THIS store, not the seeded demo store.
  const hosted = await page.locator(".storefront-link").getAttribute("href");
  const merchantId = new URL(hosted ?? "", page.url()).searchParams.get("merchant") ?? "";
  console.log(`  created ${merchantId} with key ${key.slice(0, 6)}…`);
  expect(merchantId).toMatch(/^m_/);

  // Dismissing the reminder keeps it dismissed across a reload.
  await page.getByRole("button", { name: /I have saved it/ }).click();
  await expect(page.locator(".key-banner")).toHaveCount(0);
  await page.reload();
  await expect(page.locator(".storefront-link span")).toHaveText(storeName, { timeout: 30_000 });
  await expect(page.locator(".key-banner")).toHaveCount(0);
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

  // Switching store returns to the gate, where this browser now remembers the store.
  await page.getByRole("button", { name: "Switch store" }).click();
  await expect(page.getByRole("heading", { name: "Open your store" })).toBeVisible();
  const remembered = page.locator(".gate-store", { hasText: storeName });
  await expect(remembered).toBeVisible();

  // One click reopens it - no key to find, no key to paste.
  await remembered.click();
  await expect(page.locator(".storefront-link span")).toHaveText(storeName, { timeout: 30_000 });
  console.log("  reopened", storeName, "from the remembered list");

  // Forgetting it on this device puts the key back in charge, and the key still works.
  await page.getByRole("button", { name: "Switch store" }).click();
  await page.getByRole("button", { name: new RegExp(`Forget ${storeName}`) }).click();
  await expect(page.locator(".gate-store", { hasText: storeName })).toHaveCount(0);
  await page.getByRole("button", { name: /I have a store key/ }).click();
  await page.getByPlaceholder("mk_…").fill(key);
  await page.getByRole("button", { name: "Open", exact: true }).click();
  await expect(page.locator(".storefront-link span")).toHaveText(storeName, { timeout: 30_000 });
  console.log("  signed back in to", storeName);

  expect(consoleErrors).toEqual([]);
});
