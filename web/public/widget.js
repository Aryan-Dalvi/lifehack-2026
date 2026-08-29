(() => {
  const script = document.currentScript;
  if (!script) return;
  const merchant = script.dataset.merchant || "m_mysa";
  const position = script.dataset.position || "bottom-right";
  const origin = new URL(script.src).origin;

  const host = document.createElement("div");
  host.id = "sway-commerce-widget";
  host.style.position = "fixed";
  host.style.zIndex = "2147483000";
  host.style.bottom = "20px";
  host.style[position.includes("left") ? "left" : "right"] = "20px";
  document.body.appendChild(host);

  const root = host.attachShadow({ mode: "open" });
  const style = document.createElement("style");
  style.textContent = `
    button { border: 0; font: 600 14px/1 system-ui,sans-serif; cursor: pointer; }
    .launcher { width: 58px; height: 58px; border-radius: 50%; color: white; background: #435744;
      box-shadow: 0 16px 45px rgba(25,35,26,.25); display:grid;place-items:center; }
    .launcher:focus-visible { outline: 3px solid #ff6b58; outline-offset: 3px; }
    .frame { display:none; width:min(1040px,calc(100vw - 32px)); height:min(760px,calc(100vh - 98px));
      border:1px solid #d8dad4;border-radius:20px;background:#fff;box-shadow:0 30px 90px rgba(25,35,26,.24);overflow:hidden; }
    .frame.open { display:block; }
    iframe { width:100%;height:100%;border:0;background:#fff; }
    .close { position:absolute;right:10px;top:10px;width:36px;height:36px;border-radius:50%;background:#fff;color:#1f2820;
      border:1px solid #d8dad4;box-shadow:0 4px 12px rgba(0,0,0,.12); }
    @media (max-width:700px) { .frame { position:fixed; inset:8px; width:auto;height:auto;border-radius:16px; } }
  `;
  const launcher = document.createElement("button");
  launcher.className = "launcher";
  launcher.setAttribute("aria-label", "Open Mysa Skin shopping assistant");
  launcher.textContent = "S";

  const frame = document.createElement("div");
  frame.className = "frame";
  const close = document.createElement("button");
  close.className = "close";
  close.setAttribute("aria-label", "Close shopping assistant");
  close.textContent = "×";
  const iframe = document.createElement("iframe");
  iframe.title = "Mysa Skin conversational storefront";
  iframe.src = `${origin}/storefront?merchant=${encodeURIComponent(merchant)}&embedded=1`;
  iframe.setAttribute("sandbox", "allow-scripts allow-forms allow-same-origin");
  frame.append(close, iframe);
  root.append(style, frame, launcher);

  const setOpen = (open) => {
    frame.classList.toggle("open", open);
    launcher.style.display = open ? "none" : "grid";
    if (open) close.focus();
  };
  launcher.addEventListener("click", () => setOpen(true));
  close.addEventListener("click", () => setOpen(false));
  window.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && frame.classList.contains("open")) setOpen(false);
  });
})();

