import { expect, test } from "@playwright/test";

/**
 * A merchant who publishes their storefront before uploading a catalog. This is a normal
 * state — it is what every merchant is for the first minute — and the shopper used to be
 * shown a "Shop by category" table with a header row and nothing under it.
 */

const ASK = "Ask about skincare products";

async function emptyPublishedStore(request: import("@playwright/test").APIRequestContext) {
  const created = await (
    await request.post("/api/merchant/onboard", {
      data: { name: "Bare Shelf Botanicals", size: "sme", category: "skincare" },
    })
  ).json();
  await request.put(`/api/merchant/${created.merchant_id}/config`, {
    data: { status: "published" },
    headers: { "X-Merchant-Key": created.api_key },
  });
  return created.merchant_id as string;
}

test("a shop with no catalog says so, rather than drawing an empty table", async ({
  page,
  request,
}) => {
  const merchantId = await emptyPublishedStore(request);

  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto(`/storefront?merchant=${merchantId}`);
  await page.getByRole("textbox", { name: ASK }).fill("what products do you have?");
  await page.getByRole("button", { name: "Send message" }).click();

  const reply = page.locator(".message--assistant").last();
  await expect(reply).toContainText("Bare Shelf Botanicals", { timeout: 25_000 });
  await expect(reply).toContainText("not added any products yet");

  // The thing that was reported: no empty table, and no empty results rail either.
  await expect(page.locator(".category-browser")).toHaveCount(0);
  await expect(page.locator(".product-card")).toHaveCount(0);
  await expect(page.locator(".results-section")).toHaveCount(0);
  await page.screenshot({ path: "test-results/empty-shop.png" });
});

test("the shopper is never told they are in the seeded demo store", async ({ page, request }) => {
  const merchantId = await emptyPublishedStore(request);

  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto(`/storefront?merchant=${merchantId}`);
  await expect(page.locator(".shopper-header .brand span")).toHaveText("Bare Shelf Botanicals");

  // The trust rail names the shop whose facts it is vouching for. It lives behind the
  // Purchase Protection disclosure in the cart, so open it the way a shopper would.
  await page.getByRole("button", { name: /Visa Purchase Protection/ }).click();
  await expect(page.getByText("Product facts come from Bare Shelf Botanicals.")).toBeVisible();

  await page.getByRole("textbox", { name: ASK }).fill("who are you?");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(page.locator(".message--assistant").last()).toContainText("Bare Shelf", {
    timeout: 25_000,
  });

  const wholePage = (await page.locator("body").innerText()).replace(/\s+/g, " ");
  expect(wholePage, "another merchant's storefront named the demo store").not.toContain("Mysa");
});

test("the seeded store still shows its catalog", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto("/storefront?merchant=m_mysa");
  await page.getByRole("textbox", { name: ASK }).fill("what categories do you have?");
  await page.getByRole("button", { name: "Send message" }).click();

  const browser = page.locator(".category-browser");
  await expect(browser).toBeVisible({ timeout: 25_000 });
  expect(await browser.locator("tbody tr").count()).toBeGreaterThan(0);
  await page.getByRole("button", { name: /Visa Purchase Protection/ }).click();
  await expect(page.getByText("Product facts come from Mysa Skin.")).toBeVisible();
});
