import { expect, test } from "@playwright/test";

/**
 * The browsing half of the shopper surface: asking in the chat for a comparison or for the
 * categories, opening a product, and the two layout faults that hid things behind other
 * things. Each of these was reported from the running app, so each is checked in it.
 */

const ASK = "Ask about skincare products";

test("asking to compare in the chat brings up the comparison table", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });

  await page.setViewportSize({ width: 1584, height: 1024 });
  await page.goto("/storefront?merchant=m_mysa");
  await page.getByRole("textbox", { name: ASK }).fill("I have dry sensitive skin, what should I use?");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(page.locator(".product-card").first()).toBeVisible();
  expect(await page.locator(".product-card").count()).toBeGreaterThanOrEqual(2);

  // No SKUs named and no checkboxes ticked: what is on screen is what "these" means.
  await page.getByRole("textbox", { name: ASK }).fill("compare these");
  await page.getByRole("button", { name: "Send message" }).click();

  const comparison = page.locator(".comparison-drawer");
  await expect(comparison).toBeVisible();
  await expect(comparison.getByText("Built in code from current catalog rows · 0 model calls")).toBeVisible();
  expect(await comparison.locator("thead th").count()).toBeGreaterThanOrEqual(3);
  await page.screenshot({ path: "test-results/shopper-chat-comparison.png" });
  expect(consoleErrors).toEqual([]);
});

test("asking for categories brings up a table that opens each one", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });

  await page.setViewportSize({ width: 1584, height: 1024 });
  await page.goto("/storefront?merchant=m_mysa");
  await page.getByRole("textbox", { name: ASK }).fill("what categories do you have?");
  await page.getByRole("button", { name: "Send message" }).click();

  const browser = page.locator(".category-browser");
  await expect(browser.getByRole("heading", { name: "Shop by category" })).toBeVisible();
  await expect(browser.getByRole("rowheader", { name: "Cleansers" })).toBeVisible();
  await expect(browser.getByRole("rowheader", { name: "Sunscreens" })).toBeVisible();
  await page.screenshot({ path: "test-results/shopper-categories.png" });

  await browser.getByRole("button", { name: "Browse Cleansers" }).click();
  await expect(page.getByRole("heading", { name: "Grounded options for you" })).toBeVisible();
  await expect(page.locator(".product-card").first()).toBeVisible();
  expect(consoleErrors).toEqual([]);
});

test("a product card opens its own detail dialog and nothing covers the card on hover", async ({ page }) => {
  await page.setViewportSize({ width: 1584, height: 1024 });
  await page.goto("/storefront?merchant=m_mysa");
  await page.getByRole("textbox", { name: ASK }).fill("I have dry sensitive skin, what should I use?");
  await page.getByRole("button", { name: "Send message" }).click();
  const card = page.locator(".product-card").first();
  await expect(card).toBeVisible();

  // The old hover overlay sat on top of the card it belonged to: the title, price and both
  // buttons were unreachable while the pointer was on the card. It is gone.
  const title = card.locator(".product-copy h3, .product-copy strong").first();
  await card.hover();
  await expect(page.locator(".product-preview")).toHaveCount(0);
  await expect(card.getByRole("button", { name: /Add to cart|Add another/ })).toBeVisible();

  await title.click();
  const detail = page.locator(".product-detail-sheet");
  await expect(detail).toBeVisible();
  await expect(detail.getByText("Routine step")).toBeVisible();
  await expect(detail.getByText("Key ingredients")).toBeVisible();
  await page.screenshot({ path: "test-results/shopper-product-detail.png" });

  // The dialog can add to the basket, which is the point of opening it.
  await detail.getByRole("button", { name: /Add to cart/ }).click();
  await detail.getByRole("button", { name: "Close product details" }).click();
  await expect(detail).toHaveCount(0);
  await expect(page.getByRole("button", { name: /^Checkout · S\$/ })).toBeVisible();
});

test("the trust strip never sits on top of the chat input", async ({ page }) => {
  for (const size of [
    { width: 1584, height: 1024 },
    { width: 1180, height: 820 },
    { width: 390, height: 844 },
  ]) {
    await page.setViewportSize(size);
    await page.goto("/storefront?merchant=m_mysa");
    const input = page.getByRole("textbox", { name: ASK });
    await expect(input).toBeVisible();

    // Polled rather than measured once: a viewport change can be read mid-layout, and the
    // question being asked is whether the settled layout overlaps, which it must never.
    await expect
      .poll(
        async () =>
          page.evaluate(() => {
            const composer = document.querySelector("#shopper-message");
            const strip = document.querySelector(".security-footer");
            if (!composer || !strip) return "no-strip";
            const a = composer.getBoundingClientRect();
            const b = strip.getBoundingClientRect();
            const overlaps =
              a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;
            return overlaps ? "overlaps" : "clear";
          }),
        { message: `trust strip overlaps the composer at ${size.width}px` },
      )
      .not.toBe("overlaps");

    // And the composer still takes the click that lands on it.
    await input.click();
    await expect(input).toBeFocused();
  }
});

test("a product the agent names in an answer is bold, with its card beside the message", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1584, height: 1024 });
  await page.goto("/storefront?merchant=m_mysa");
  await page.getByRole("textbox", { name: ASK }).fill("is the Gentle Cloud Cleanser fragrance free?");
  await page.getByRole("button", { name: "Send message" }).click();

  // Wait for the agent's reply, then judge the rule rather than the model's word choice:
  // whatever it says, a product it names must be bold and must have its card attached.
  // The answer comes from a model call, which is slower than a default expect timeout.
  await expect(page.locator(".message--assistant")).not.toHaveCount(1, { timeout: 25_000 });
  await expect(page.locator(".thinking")).toHaveCount(0);
  const reply = page.locator(".message--assistant").last();
  await expect(reply).toBeVisible();

  const text = ((await reply.innerText()) ?? "").trim();
  const named = "Gentle Cloud Cleanser";
  if (text.includes(named)) {
    const bold = reply.locator(".named-product", { hasText: named });
    await expect(bold.first()).toBeVisible();
    // The card for that product sits under the message that named it.
    const attached = page.locator(".message-products .product-card");
    await expect(attached.first()).toBeVisible();
    await expect(attached.first()).toContainText(named);
    await page.screenshot({ path: "test-results/shopper-named-product.png" });
  } else {
    // The agent answered without naming it; it must still have shown something grounded.
    await expect(page.locator(".product-card").first()).toBeVisible();
  }
});
