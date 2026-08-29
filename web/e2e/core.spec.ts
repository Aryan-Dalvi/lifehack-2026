import { expect, test } from "@playwright/test";

test("shopper completes discover, compare, consent, bank and payment", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });

  await page.setViewportSize({ width: 1584, height: 1024 });
  await page.goto("/storefront?merchant=m_mysa");
  await expect(page.getByRole("heading", { name: "What does your skin need today?" })).toBeVisible();
  // The shopper starts by asking, not by picking a chip.
  await page
    .getByRole("textbox", { name: "Ask about skincare products" })
    .fill("I have dry sensitive skin, what should I use?");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(page.getByRole("heading", { name: "Grounded options for you" })).toBeVisible();
  await expect(page.locator(".product-card")).toHaveCount(3);

  await page.locator(".product-card").nth(0).getByRole("button", { name: "Compare" }).click();
  await page.locator(".product-card").nth(1).getByRole("button", { name: "Compare" }).click();
  await page.getByRole("button", { name: /Compare 2 products/ }).click();
  await expect(page.getByText("Built in code from current catalog rows · 0 model calls")).toBeVisible();
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: "test-results/shopper-products.png" });

  // Choosing from the comparison puts the product in the cart; checkout is the cart's job.
  await page.getByRole("button", { name: /^Choose / }).first().click();
  await page.getByRole("button", { name: "Close comparison" }).click();

  // Guest checkout stops for want of a shipping address, which is what an account is for.
  await page.getByRole("button", { name: /^Checkout · S\$/ }).click();
  await expect(page.getByText("Add a shipping address before checkout.")).toBeVisible();

  // Signing in attaches the account to the session in progress - the basket survives.
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.getByLabel("Email").fill("demo@mysa.test");
  await page.getByLabel("Password").fill("mysa-demo-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).last().click();
  await expect(page.getByText("N. Shopper")).toBeVisible();

  await page.getByRole("button", { name: /^Checkout · S\$/ }).click();
  await expect(page.getByRole("heading", { name: "Confirm this exact purchase" })).toBeVisible();
  await page.getByRole("button", { name: /Confirm & pay/ }).click();
  await expect(page.getByRole("heading", { name: /Approve S\$/ })).toBeVisible();
  await page.getByLabel("Verification code").fill("492118");
  await page.getByRole("button", { name: "Verify and continue" }).click();
  await expect(page.getByText("Order confirmed")).toBeVisible();
  await expect(page.getByText("Simulated authorization · no real charge")).toBeVisible();
  await page.locator(".receipt-card").screenshot({ path: "test-results/shopper-receipt.png" });
  // This test deliberately attempts a guest checkout, and the browser logs that rejected
  // request as a console error. Everything else must still be clean.
  expect(consoleErrors.filter((line) => !line.includes("409"))).toEqual([]);
});

test("merchant onboarding and both deployment options render", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });

  await page.setViewportSize({ width: 1584, height: 1024 });
  // The admin page reads one merchant's private config, so it needs that merchant's key.
  // Seeding writes the local key to var/merchant-key.txt; MERCHANT_KEY carries it in CI.
  await page.addInitScript((key) => {
    window.localStorage.setItem("sway.merchantKey", key);
  }, process.env.MERCHANT_KEY ?? "");
  await page.goto("/admin");
  await expect(page.getByRole("heading", { name: "Make your catalog conversational" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Website widget" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Hosted storefront" })).toBeVisible();
  await expect(page.getByText("Fixed for Phase 0")).toBeVisible();
  await expect(page.getByRole("link", { name: "Open hosted storefront QR code" })).toBeVisible();
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
  await commerceCanvas
    .getByRole("textbox", { name: "Ask about skincare products" })
    .fill("I have dry sensitive skin, what should I use?");
  await commerceCanvas.getByRole("button", { name: "Send message" }).click();
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

test("landing home page renders with hero mockup, marquee, and onboarding flow", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });

  await page.setViewportSize({ width: 1584, height: 1024 });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Turn conversations into trusted sales/i })).toBeVisible();
  await expect(page.getByText("The 90-Second Conversational Commerce Platform")).toBeVisible();
  await expect(page.getByText("Built on Visa's trust and payment network")).toBeVisible();
  await expect(page.getByRole("heading", { name: /From catalog to AI commerce in 90 seconds/i })).toBeVisible();
  await expect(page.getByRole("link", { name: "Get started in 90 seconds" }).first()).toBeVisible();
  await page.screenshot({ path: "test-results/landing-page.png", fullPage: true });
  expect(consoleErrors).toEqual([]);
});
