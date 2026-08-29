import { createServer, type Server } from "node:http";
import { expect, test } from "@playwright/test";

/**
 * The embeddable widget, exercised the way a merchant actually installs it: one script tag
 * on a page served from a **different origin**. `widget-demo.html` is same-origin and so
 * cannot catch anything that only breaks across origins.
 *
 * The host page is served by the suite itself, so this needs no fixture site on disk.
 */

const WIDGET_ORIGIN = process.env.PLAYWRIGHT_WIDGET_ORIGIN ?? "http://127.0.0.1:5173";
const HOST_PORT = Number(process.env.PLAYWRIGHT_WIDGET_HOST_PORT ?? 5199);
const HOST_ORIGIN = `http://127.0.0.1:${HOST_PORT}`;

/**
 * The merchant's own site, served for real.
 *
 * It has to be a real listener rather than an intercepted route: a browser refuses to let a
 * page it considers public load a subresource from the loopback address space (Private
 * Network Access), and a fulfilled route counts as public however its URL reads. That block
 * would fail the fixture rather than the product.
 */
let server: Server;
let hostBody = "";

function hostPage(attrs = 'data-merchant="m_mysa" data-position="bottom-right"'): string {
  return `<!doctype html>
    <html lang="en"><head><meta charset="utf-8"><title>Retailer</title>
    <style>body{margin:0;font-family:system-ui;padding:40px}h1{font-size:40px}</style></head>
    <body><h1>An existing merchant website</h1>
    <p>The launcher below is installed with one script tag.</p>
    <script src="${WIDGET_ORIGIN}/widget.js" ${attrs}></script>
    </body></html>`;
}

test.beforeAll(async () => {
  server = createServer((_request, response) => {
    response.writeHead(200, { "content-type": "text/html; charset=utf-8" });
    response.end(hostBody || hostPage());
  });
  await new Promise<void>((resolve) => server.listen(HOST_PORT, "127.0.0.1", resolve));
});

test.afterAll(async () => {
  await new Promise<void>((resolve) => server.close(() => resolve()));
});

test.beforeEach(() => {
  hostBody = "";
});

async function openHost(page: import("@playwright/test").Page, attrs?: string) {
  hostBody = hostPage(attrs);
  await page.goto(`${HOST_ORIGIN}/`);
}

const widget = (page: import("@playwright/test").Page) => page.locator("#sway-commerce-widget");

test("one script tag on someone else's site puts a branded launcher on the page", async ({ page }) => {
  const problems: string[] = [];
  page.on("pageerror", (error) => problems.push(String(error)));

  await page.setViewportSize({ width: 1440, height: 900 });
  await openHost(page);

  const launcher = widget(page).locator("button.launcher");
  await expect(launcher).toBeVisible();
  // The launcher wears the merchant's own name and accent, read from the public profile.
  await expect(launcher).toContainText("Ask Mysa Skin", { timeout: 10_000 });
  await expect(launcher).toContainText("Powered by Sway");
  const accent = await widget(page).evaluate((host) => {
    const layer = host.shadowRoot?.querySelector(".layer") as HTMLElement;
    return getComputedStyle(layer).getPropertyValue("--accent").trim();
  });
  expect(accent).toBe("#6f8066");

  // Nothing of the storefront is fetched until someone asks for it.
  const srcBeforeOpen = await widget(page).evaluate(
    (host) => (host.shadowRoot?.querySelector("iframe") as HTMLIFrameElement).getAttribute("src"),
  );
  expect(srcBeforeOpen).toBeNull();

  await page.screenshot({ path: "test-results/widget-launcher.png" });
  expect(problems).toEqual([]);
});

test("opening it shows the storefront, and the close button hits nothing else", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await openHost(page);

  await widget(page).locator("button.launcher").click();
  const storefront = page.frameLocator("#sway-commerce-widget iframe");
  await expect(storefront.getByRole("heading", { name: "What does your skin need today?" })).toBeVisible({
    timeout: 20_000,
  });
  await page.screenshot({ path: "test-results/widget-open.png" });

  // The close button used to sit on top of the storefront's own header, directly over its
  // "Sign in" control. It now lives in the panel's chrome bar, above the app entirely.
  const overlap = await widget(page).evaluate((host) => {
    const root = host.shadowRoot as ShadowRoot;
    const close = (root.querySelector(".close") as HTMLElement).getBoundingClientRect();
    const frame = (root.querySelector("iframe") as HTMLElement).getBoundingClientRect();
    return close.bottom > frame.top && close.top < frame.bottom;
  });
  expect(overlap, "the close button overlaps the storefront").toBe(false);

  // And the storefront's sign-in control is reachable rather than covered.
  await expect(storefront.getByRole("button", { name: "Sign in" })).toBeVisible();

  // The panel carries the merchant's name once, not twice: the chrome bar says it, and the
  // storefront's own brand block is hidden while embedded.
  await expect(widget(page).locator(".chrome-title")).toHaveText("Mysa Skin");
  await expect(storefront.locator(".shopper-header .brand")).toBeHidden();
});

test("it closes from the backdrop, the button, and Escape inside the chat", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await openHost(page);
  const launcher = widget(page).locator("button.launcher");
  const layer = widget(page).locator(".layer");

  await launcher.click();
  await expect(layer).toHaveClass(/open/);
  await widget(page).locator("button.close").click();
  await expect(layer).not.toHaveClass(/open/);
  await expect(launcher).toBeVisible();

  // Clicking the merchant's own page behind the panel dismisses it.
  await launcher.click();
  await expect(layer).toHaveClass(/open/);
  await widget(page).locator(".backdrop").click({ position: { x: 20, y: 20 } });
  await expect(layer).not.toHaveClass(/open/);

  // Escape pressed while typing in the chat used to do nothing: the key never leaves the
  // iframe. The storefront now tells its host, and the host checks who asked.
  await launcher.click();
  const storefront = page.frameLocator("#sway-commerce-widget iframe");
  await storefront.getByRole("textbox", { name: "Ask about skincare products" }).click();
  await page.keyboard.press("Escape");
  await expect(layer).not.toHaveClass(/open/);
});

test("a second script tag does not stack a second launcher", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  hostBody = `<!doctype html><html><body>
    <script src="${WIDGET_ORIGIN}/widget.js" data-merchant="m_mysa"></script>
    <script src="${WIDGET_ORIGIN}/widget.js" data-merchant="m_mysa"></script>
  </body></html>`;
  await page.goto(`${HOST_ORIGIN}/`);
  await expect(page.locator("#sway-commerce-widget")).toHaveCount(1);
  await expect(widget(page).locator("button.launcher")).toHaveCount(1);
});

test("the panel goes full-bleed on a phone and the page never scrolls sideways", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await openHost(page);

  // The label collapses to the mark alone, so the launcher does not eat a phone screen.
  const launcher = widget(page).locator("button.launcher");
  await expect(launcher).toBeVisible();
  expect((await launcher.boundingBox())?.width ?? 999).toBeLessThan(110);

  await launcher.click();

  // Polled, because the panel scales into place: a rect read mid-transition is the animated
  // box, not the laid-out one. What matters is where it comes to rest.
  await expect
    .poll(async () =>
      widget(page).evaluate((host) => {
        const panel = (host.shadowRoot?.querySelector(".panel") as HTMLElement).getBoundingClientRect();
        const root = document.documentElement;
        const fills = Math.round(panel.x) === 0 && Math.round(panel.width) === root.clientWidth;
        return fills
          ? "full-bleed"
          : `x=${Math.round(panel.x)} w=${Math.round(panel.width)} of ${root.clientWidth}`;
      }),
    )
    .toBe("full-bleed");

  const scroll = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }));
  expect(scroll.scrollWidth).toBeLessThanOrEqual(scroll.clientWidth);
  await page.screenshot({ path: "test-results/widget-mobile.png" });
});

test("an unreachable brand lookup still leaves a working launcher", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  // The storefront must open even when the merchant's public profile cannot be read.
  await page.route("**/api/merchant/*/profile", (route) => route.abort());
  await openHost(page);

  const launcher = widget(page).locator("button.launcher");
  await expect(launcher).toBeVisible();
  await expect(launcher).toContainText("Ask about skincare");
  await launcher.click();
  await expect(
    page.frameLocator("#sway-commerce-widget iframe").getByRole("heading", { name: "What does your skin need today?" }),
  ).toBeVisible({ timeout: 20_000 });
});
