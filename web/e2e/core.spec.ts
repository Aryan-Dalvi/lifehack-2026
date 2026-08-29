import { expect, test } from "@playwright/test";

test("shopper completes discover, compare, consent, bank and payment", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });

  await page.setViewportSize({ width: 1584, height: 1024 });
  await page.goto("/storefront?merchant=m_mysa");
  await expect(page.getByRole("heading", { name: "What does your skin need today?" })).toBeVisible();
  await page.getByRole("button", { name: "Dryness" }).click();
  await expect(page.getByRole("heading", { name: "Grounded options for you" })).toBeVisible();
  await expect(page.locator(".product-card")).toHaveCount(3);

  await page.locator(".product-card .text-action").nth(0).click();
  await page.locator(".product-card .text-action").nth(1).click();
  await page.getByRole("button", { name: /Compare 2 products/ }).click();
  await expect(page.getByText("Built in code from current catalog rows · 0 model calls")).toBeVisible();
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: "test-results/shopper-products.png" });

  await page.locator(".comparison-drawer .table-action").first().click();
  await expect(page.getByRole("heading", { name: "Confirm this exact purchase" })).toBeVisible();
  await page.getByRole("button", { name: /Confirm & pay/ }).click();
  await expect(page.getByRole("heading", { name: /Approve S\$/ })).toBeVisible();
  await page.getByLabel("Verification code").fill("492118");
  await page.getByRole("button", { name: "Verify and continue" }).click();
  await expect(page.getByText("Order confirmed")).toBeVisible();
  await expect(page.getByText("Simulated authorization · no real charge")).toBeVisible();
  await page.locator(".receipt-card").screenshot({ path: "test-results/shopper-receipt.png" });
  expect(consoleErrors).toEqual([]);
});

test("merchant onboarding and both deployment options render", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });

  await page.setViewportSize({ width: 1584, height: 1024 });
  await page.goto("/admin");
  await expect(page.getByRole("heading", { name: "Make your catalog conversational" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Website widget" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Hosted storefront" })).toBeVisible();
  await expect(page.getByText("Fixed for Phase 0")).toBeVisible();
  await page.screenshot({ path: "test-results/merchant-admin.png" });
  expect(consoleErrors).toEqual([]);
});

test("one-line merchant widget opens an isolated storefront without redirecting", async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 900 });
  await page.goto("/widget-demo.html");
  await page.getByRole("button", { name: "Open Mysa Skin shopping assistant" }).click();
  await expect(page).toHaveURL(/widget-demo\.html$/);

  const iframe = page.locator('iframe[title="Mysa Skin conversational storefront"]');
  await expect(iframe).toHaveAttribute("sandbox", "allow-scripts allow-forms allow-same-origin");
  const commerceCanvas = page.frameLocator('iframe[title="Mysa Skin conversational storefront"]');
  await expect(
    commerceCanvas.getByRole("heading", { name: "What does your skin need today?" }),
  ).toBeVisible();
  await commerceCanvas.getByRole("button", { name: "Dryness" }).click();
  await expect(commerceCanvas.locator(".product-card")).toHaveCount(3);
  await expect(page).toHaveURL(/widget-demo\.html$/);
});

test("shopper surface stays within a mobile viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/storefront?merchant=m_mysa&embedded=1");
  await expect(page.getByRole("heading", { name: "What does your skin need today?" })).toBeVisible();
  const width = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    client: document.documentElement.clientWidth,
  }));
  expect(width.scroll).toBeLessThanOrEqual(width.client);
  await page.screenshot({ path: "test-results/shopper-mobile.png", fullPage: true });
});
