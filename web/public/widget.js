/**
 * The one-line embed: a launcher on the merchant's own site that opens their shopping agent
 * in a sandboxed iframe.
 *
 *   <script src="https://…/widget.js" data-merchant="m_…" data-position="bottom-right"></script>
 *
 * Everything lives inside a shadow root, so the host page's CSS cannot reach in and this
 * cannot leak out. The only network call it makes on its own is for the merchant's public
 * brand (name, accent, logo) — the panel itself is just an iframe of the real storefront.
 *
 * Optional attributes: data-label, data-accent, data-open ("1" opens on load).
 */
(() => {
  const script =
    document.currentScript ||
    document.querySelector('script[data-merchant][src*="widget.js"]') ||
    document.querySelector('script[src*="widget.js"]');
  if (!script) return;
  // Two copies of the tag, or a re-run after a client-side navigation, must not stack two
  // launchers on the page.
  if (document.getElementById("sway-commerce-widget")) return;

  const merchant = script.dataset.merchant || "m_mysa";
  const position = (script.dataset.position || "bottom-right").includes("left") ? "left" : "right";
  const origin = new URL(script.src, window.location.href).origin;
  const reduceMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;

  const brand = {
    // `name` is the merchant, once known. `label` is what the launcher says — they are not
    // the same string: before the profile arrives there is no name to put in front of "Ask".
    name: null,
    label: script.dataset.label || null,
    accent: script.dataset.accent || "#435744",
    logo: null,
  };

  const host = document.createElement("div");
  host.id = "sway-commerce-widget";
  document.body.appendChild(host);
  const root = host.attachShadow({ mode: "open" });

  const style = document.createElement("style");
  style.textContent = `
    :host { all: initial; }
    * { box-sizing: border-box; }
    button { font: inherit; cursor: pointer; }

    .layer {
      position: fixed;
      inset: 0;
      z-index: 2147483000;
      font-family: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: #20251f;
      pointer-events: none;
    }

    /* Launcher ------------------------------------------------------------ */

    .launcher {
      position: absolute;
      bottom: 20px;
      ${position}: 20px;
      pointer-events: auto;
      display: inline-flex;
      align-items: center;
      gap: 10px;
      max-width: min(320px, calc(100vw - 40px));
      height: 56px;
      padding: 0 22px 0 8px;
      border: 0;
      border-radius: 999px;
      color: #fff;
      background: var(--accent, #435744);
      box-shadow: 0 10px 30px rgba(25, 35, 26, 0.28);
      transition: transform 180ms ease, box-shadow 180ms ease, opacity 160ms ease;
    }

    .launcher:hover { transform: translateY(-2px); box-shadow: 0 16px 40px rgba(25,35,26,.34); }
    .launcher:active { transform: translateY(0); }
    .launcher:focus-visible { outline: 3px solid #fff; outline-offset: 3px; }
    .launcher[hidden] { display: none; }

    .launcher-mark {
      flex: 0 0 40px;
      width: 40px;
      height: 40px;
      border-radius: 50%;
      display: grid;
      place-items: center;
      overflow: hidden;
      background: rgba(255, 255, 255, 0.18);
      font-size: 17px;
      font-weight: 700;
    }

    .launcher-mark img { width: 100%; height: 100%; object-fit: cover; }

    .launcher-text {
      display: grid;
      gap: 1px;
      text-align: left;
      min-width: 0;
    }

    .launcher-text strong {
      font-size: 14px;
      font-weight: 650;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .launcher-text small { font-size: 11px; opacity: 0.82; white-space: nowrap; }

    /* A quiet pulse on first paint, so the launcher is noticed once and then left alone. */
    .launcher::after {
      content: "";
      position: absolute;
      inset: 0;
      border-radius: inherit;
      border: 2px solid var(--accent, #435744);
      opacity: 0;
      animation: sway-ping 2.6s ease-out 2;
    }

    @keyframes sway-ping {
      0% { opacity: .55; transform: scale(1); }
      70%, 100% { opacity: 0; transform: scale(1.35); }
    }

    /* Panel --------------------------------------------------------------- */

    .backdrop {
      position: absolute;
      inset: 0;
      background: rgba(24, 30, 24, 0.42);
      opacity: 0;
      pointer-events: none;
      transition: opacity 220ms ease;
    }

    .panel {
      position: absolute;
      bottom: 20px;
      ${position}: 20px;
      pointer-events: none;
      display: flex;
      flex-direction: column;
      width: min(1040px, calc(100vw - 40px));
      height: min(760px, calc(100vh - 40px));
      border-radius: 20px;
      background: #fdfcf9;
      box-shadow: 0 40px 100px rgba(20, 28, 20, 0.32);
      overflow: hidden;
      opacity: 0;
      transform: translateY(14px) scale(0.985);
      transform-origin: bottom ${position};
      transition: opacity 200ms ease, transform 220ms cubic-bezier(0.22, 1, 0.36, 1);
    }

    .layer.open .backdrop { opacity: 1; pointer-events: auto; }
    .layer.open .panel { opacity: 1; pointer-events: auto; transform: none; }

    .chrome {
      flex: 0 0 auto;
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 10px 12px 10px 14px;
      border-bottom: 1px solid rgba(20, 28, 20, 0.1);
      background: var(--accent, #435744);
      color: #fff;
    }

    .chrome-mark {
      flex: 0 0 26px;
      width: 26px;
      height: 26px;
      border-radius: 50%;
      display: grid;
      place-items: center;
      overflow: hidden;
      background: rgba(255, 255, 255, 0.2);
      font-size: 12px;
      font-weight: 700;
    }

    .chrome-mark img { width: 100%; height: 100%; object-fit: cover; }

    .chrome-title {
      flex: 1;
      min-width: 0;
      font-size: 13px;
      font-weight: 650;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .chrome-by { font-size: 11px; opacity: 0.78; white-space: nowrap; }

    .close {
      flex: 0 0 32px;
      width: 32px;
      height: 32px;
      display: grid;
      place-items: center;
      border: 0;
      border-radius: 50%;
      color: inherit;
      background: rgba(255, 255, 255, 0.16);
      transition: background 150ms ease;
    }

    .close:hover { background: rgba(255, 255, 255, 0.3); }
    .close:focus-visible { outline: 2px solid #fff; outline-offset: 2px; }

    .surface { position: relative; flex: 1; min-height: 0; }

    iframe { display: block; width: 100%; height: 100%; border: 0; background: #fdfcf9; }

    .loading {
      position: absolute;
      inset: 0;
      display: grid;
      place-items: center;
      gap: 10px;
      background: #fdfcf9;
      color: #6f746d;
      font-size: 13px;
      transition: opacity 200ms ease;
    }

    .loading[hidden] { display: none; }

    .spinner {
      width: 22px;
      height: 22px;
      border-radius: 50%;
      border: 2px solid rgba(67, 87, 68, 0.25);
      border-top-color: var(--accent, #435744);
      animation: sway-spin 900ms linear infinite;
    }

    @keyframes sway-spin { to { transform: rotate(360deg); } }

    @media (max-width: 760px) {
      .launcher { padding-right: 8px; }
      .launcher-text { display: none; }
      .panel {
        inset: 0;
        width: auto;
        height: auto;
        border-radius: 0;
      }
    }

    @media (prefers-reduced-motion: reduce) {
      .launcher, .panel, .backdrop { transition: none; }
      .launcher::after { animation: none; }
      .spinner { animation-duration: 2s; }
    }
  `;

  const layer = document.createElement("div");
  layer.className = "layer";
  layer.style.setProperty("--accent", brand.accent);

  const backdrop = document.createElement("div");
  backdrop.className = "backdrop";

  const launcher = document.createElement("button");
  launcher.type = "button";
  launcher.className = "launcher";
  const launcherMark = document.createElement("span");
  launcherMark.className = "launcher-mark";
  launcherMark.setAttribute("aria-hidden", "true");
  launcherMark.textContent = "S";
  const launcherText = document.createElement("span");
  launcherText.className = "launcher-text";
  const launcherTitle = document.createElement("strong");
  launcherTitle.textContent = "Ask about skincare";
  const launcherSub = document.createElement("small");
  launcherSub.textContent = "Powered by Sway";
  launcherText.append(launcherTitle, launcherSub);
  launcher.append(launcherMark, launcherText);

  const panel = document.createElement("div");
  panel.className = "panel";
  panel.setAttribute("role", "dialog");
  panel.setAttribute("aria-modal", "true");
  panel.setAttribute("aria-label", "Shopping assistant");

  const chrome = document.createElement("div");
  chrome.className = "chrome";
  const chromeMark = document.createElement("span");
  chromeMark.className = "chrome-mark";
  chromeMark.setAttribute("aria-hidden", "true");
  chromeMark.textContent = "S";
  const chromeTitle = document.createElement("span");
  chromeTitle.className = "chrome-title";
  chromeTitle.textContent = "Shopping assistant";
  const chromeBy = document.createElement("span");
  chromeBy.className = "chrome-by";
  chromeBy.textContent = "Powered by Sway";
  const close = document.createElement("button");
  close.type = "button";
  close.className = "close";
  close.setAttribute("aria-label", "Close shopping assistant");
  close.innerHTML =
    '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M18 6 6 18M6 6l12 12"/></svg>';
  chrome.append(chromeMark, chromeTitle, chromeBy, close);

  const surface = document.createElement("div");
  surface.className = "surface";
  const loading = document.createElement("div");
  loading.className = "loading";
  const spinner = document.createElement("div");
  spinner.className = "spinner";
  const loadingText = document.createElement("span");
  loadingText.textContent = "Opening the store…";
  loading.append(spinner, loadingText);

  const iframe = document.createElement("iframe");
  iframe.title = "Conversational storefront";
  iframe.setAttribute("sandbox", "allow-scripts allow-forms allow-same-origin");
  // Loaded on first open, not on page load: an embed must not cost every visitor a
  // storefront's worth of JavaScript before they have asked for it.
  iframe.dataset.src = `${origin}/storefront?merchant=${encodeURIComponent(merchant)}&embedded=1`;
  iframe.addEventListener("load", () => {
    if (iframe.src) loading.hidden = true;
  });
  surface.append(iframe, loading);

  panel.append(chrome, surface);
  layer.append(backdrop, panel, launcher);
  root.append(style, layer);

  /** Wear the merchant's own name, colour and mark, once we know them. */
  const applyBrand = () => {
    layer.style.setProperty("--accent", brand.accent);
    const title = brand.name || "Shopping assistant";
    const label = brand.label || (brand.name ? `Ask ${brand.name}` : "Ask about skincare");
    launcherTitle.textContent = label;
    launcher.setAttribute("aria-label", `${label} — open the shopping assistant`);
    chromeTitle.textContent = title;
    panel.setAttribute("aria-label", `${title} shopping assistant`);
    iframe.title = brand.name ? `${brand.name} conversational storefront` : "Conversational storefront";
    const initial = (brand.name || "S").trim().charAt(0).toUpperCase();
    for (const mark of [launcherMark, chromeMark]) {
      if (brand.logo) {
        const image = document.createElement("img");
        image.src = brand.logo;
        image.alt = "";
        mark.replaceChildren(image);
      } else {
        mark.textContent = initial;
      }
    }
  };
  applyBrand();

  // The merchant's public brand. A failure here is silent on purpose: the widget still works
  // in Sway's own colours, and a storefront must never fail to open because a logo 404'd.
  fetch(`${origin}/api/merchant/${encodeURIComponent(merchant)}/profile`)
    .then((response) => (response.ok ? response.json() : null))
    .then((profile) => {
      if (!profile) return;
      if (profile.name) brand.name = profile.name;
      if (!script.dataset.accent && profile.accent_color) brand.accent = profile.accent_color;
      if (profile.logo_url) {
        brand.logo = profile.logo_url.startsWith("http")
          ? profile.logo_url
          : `${origin}${profile.logo_url.startsWith("/") ? "" : "/"}${profile.logo_url}`;
      }
      applyBrand();
    })
    .catch(() => {});

  let open = false;
  const setOpen = (next) => {
    if (next === open) return;
    open = next;
    layer.classList.toggle("open", open);
    launcher.hidden = open;
    if (open) {
      if (!iframe.src) iframe.src = iframe.dataset.src;
      window.setTimeout(() => close.focus(), reduceMotion ? 0 : 180);
    } else {
      launcher.focus();
    }
  };

  launcher.addEventListener("click", () => setOpen(true));
  close.addEventListener("click", () => setOpen(false));
  backdrop.addEventListener("click", () => setOpen(false));
  window.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && open) setOpen(false);
  });
  // Escape pressed *inside* the iframe never reaches this page, so the storefront says so
  // itself. Only our own frame, from our own origin, is listened to.
  window.addEventListener("message", (event) => {
    if (event.origin !== origin || event.source !== iframe.contentWindow) return;
    if (event.data && event.data.type === "sway:close") setOpen(false);
  });

  if (script.dataset.open === "1") setOpen(true);
})();
