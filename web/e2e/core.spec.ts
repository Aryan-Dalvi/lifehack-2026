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
  await expect(page.getByRole("heading", { name: "Add a shipping address" })).toBeVisible();
  await expect(page.getByText(/Sign in first, using the account menu/)).toBeVisible();
  await page.getByRole("button", { name: "Close" }).click();

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
  await page.goto("/admin/setup");
  await expect(page.getByRole("heading", { name: "Make your catalog conversational" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Website widget" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Hosted storefront" })).toBeVisible();
  await expect(page.getByText("Fixed for Phase 0")).toBeVisible();
  await expect(page.getByRole("link", { name: "Open hosted storefront QR code" })).toBeVisible();
  const template = page.getByRole("link", { name: /Download the Excel template/ });
  await expect(template).toBeVisible();
  expect((await template.boundingBox())?.height).toBeGreaterThanOrEqual(44);

  await expect(page.getByLabel("Choose brand accent color")).toBeVisible();
  await page.getByRole("button", { name: "Use Ocean accent" }).click();
  await expect(page.getByLabel("Brand accent hex value")).toHaveValue("#255B78");
  await expect(page.locator(".preview-window")).toHaveCSS("--merchant-accent", "#255B78");
  await page.screenshot({ path: "test-results/merchant-admin.png" });

  await page.setViewportSize({ width: 390, height: 844 });
  const width = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    client: document.documentElement.clientWidth,
  }));
  expect(width.scroll).toBeLessThanOrEqual(width.client);
  await page.screenshot({ path: "test-results/merchant-admin-mobile.png", fullPage: true });
  expect(consoleErrors).toEqual([]);
});

test("a published merchant lands on the CRM dashboard at /admin", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });

  await page.setViewportSize({ width: 1584, height: 1024 });
  await page.addInitScript((key) => {
    window.localStorage.setItem("sway.merchantKey", key);
  }, process.env.MERCHANT_KEY ?? "");
  await page.goto("/admin");

  // The three KPI cards, the trend, the task rail and the customer table: the whole point
  // of finishing onboarding is that this is what the merchant opens next.
  await expect(page.getByRole("heading", { name: "Revenue analytics" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Priority tasks" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Manage customers" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Customers", exact: true })).toBeVisible();

  // Earnings is a fixed metric, while the one remaining select covers its whole visual
  // control (including the chevron) and the plot does not manufacture a scrollbar.
  await expect(page.getByText("Earnings", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Earnings" })).toHaveCount(0);
  const periodSelect = page.getByLabel("Reporting period");
  const periodControl = page.locator(".crm-period-select");
  const [selectBox, controlBox] = await Promise.all([
    periodSelect.boundingBox(),
    periodControl.boundingBox(),
  ]);
  expect(selectBox).not.toBeNull();
  expect(controlBox).not.toBeNull();
  expect(Math.abs((selectBox?.width ?? 0) - (controlBox?.width ?? 0))).toBeLessThanOrEqual(1);
  expect(Math.abs((selectBox?.height ?? 0) - (controlBox?.height ?? 0))).toBeLessThanOrEqual(1);
  const chartWidth = await page.locator(".crm-chart-plot").evaluate((plot) => ({
    client: plot.clientWidth,
    scroll: plot.scrollWidth,
  }));
  expect(chartWidth.scroll).toBeLessThanOrEqual(chartWidth.client);

  // Catalog editing is a separate always-editable table; the prior purchase history remains.
  await page.getByRole("button", { name: "Products", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Catalog management" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Product purchase history" })).toBeVisible();
  await expect(page.locator(".crm-product-input--title").first()).toBeEditable();

  // At a narrower desktop width the wide editor must scroll inside its card, never underneath
  // the sticky priority/assistant rail.
  await page.setViewportSize({ width: 1280, height: 1024 });
  const [productPanelBox, railBox] = await Promise.all([
    page.locator("#product-management").boundingBox(),
    page.locator(".crm-rail").boundingBox(),
  ]);
  expect(productPanelBox).not.toBeNull();
  expect(railBox).not.toBeNull();
  expect((productPanelBox?.x ?? 0) + (productPanelBox?.width ?? 0)).toBeLessThanOrEqual(
    (railBox?.x ?? 0) + 1,
  );
  const productOverflow = await page.locator("#product-management").evaluate((panel) => {
    const scroller = panel.querySelector<HTMLElement>(".crm-table-scroll");
    const panelBounds = panel.getBoundingClientRect();
    const scrollerBounds = scroller?.getBoundingClientRect();
    return {
      panelRight: panelBounds.right,
      scrollerRight: scrollerBounds?.right ?? Number.POSITIVE_INFINITY,
      scrollsInternally: (scroller?.scrollWidth ?? 0) > (scroller?.clientWidth ?? 0),
    };
  });
  expect(productOverflow.scrollerRight).toBeLessThanOrEqual(productOverflow.panelRight + 1);
  expect(productOverflow.scrollsInternally).toBe(true);

  await page.getByRole("button", { name: "Add product" }).click();
  await expect(page.getByRole("heading", { name: "Add a product" })).toBeVisible();
  await expect(page.getByLabel("SKU", { exact: true })).toBeEditable();
  await page.getByRole("button", { name: "Cancel" }).click();
  await page.setViewportSize({ width: 1584, height: 1024 });
  await page.getByRole("button", { name: "Overview", exact: true }).click();

  // Ask it to summarise something, and the answer must arrive with its own figures.
  await page.getByRole("button", { name: "Revenue summary" }).click();
  await expect(page.getByRole("heading", { name: "Revenue and forecast" })).toBeVisible();

  await page.screenshot({ path: "test-results/merchant-dashboard.png" });
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
