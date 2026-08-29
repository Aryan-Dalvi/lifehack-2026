import { ArrowRight, Check, ChevronDown, CircleAlert, Clipboard, CloudUpload, ExternalLink, FileSpreadsheet, Link2, LoaderCircle, LockKeyhole, RefreshCw, Store } from "lucide-react";
import { QRCodeSVG } from "qrcode.react";
import { type ChangeEvent, useEffect, useState } from "react";
import { api, getMerchantKey, money, setMerchantKey } from "../../api";
import type { Product } from "../../types";

type MerchantConfig = {
  merchant_id: string;
  name: string;
  size: "sme" | "enterprise";
  category: "skincare";
  currency: string;
  accent_color: string;
  status: "draft" | "published";
  hosted_url: string;
  embed_snippet: string;
};

type UploadResult = {
  ingested: number;
  skipped: number;
  errors: Array<{ row: number; reason: string }>;
  source: { filename: string; format: string };
  mappings: Record<string, string>;
  partial_success: boolean;
};

const defaultMappings = {
  sku: "SKU",
  title: "Name",
  price_cents: "Price",
  ingredients: "Ingredients",
  skin_types: "Skin types",
  stock: "Stock",
};

export function MerchantAdmin() {
  const [config, setConfig] = useState<MerchantConfig | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [upload, setUpload] = useState<UploadResult | null>(null);
  const [uploading, setUploading] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [published, setPublished] = useState(false);
  const [copied, setCopied] = useState<"snippet" | "url" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [merchantKey, setKey] = useState<string>(getMerchantKey() ?? "");

  useEffect(() => {
    // Admin data belongs to one merchant and is read with that merchant's API key. Seeding
    // writes it to var/merchant-key.txt; onboarding returns it once.
    if (!merchantKey) {
      setError("Enter your merchant API key to load this store.");
      return;
    }
    setError(null);
    Promise.all([
      api<MerchantConfig>("/merchant/m_mysa/config"),
      api<{ results: Product[] }>("/catalog/search?merchant_id=m_mysa&category=skincare&limit=5"),
    ])
      .then(([merchant, catalog]) => {
        setConfig(merchant);
        setProducts(catalog.results);
        setPublished(merchant.status === "published");
      })
      .catch((requestError: Error) => setError(requestError.message));
  }, [merchantKey]);

  const uploadCatalog = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file || !config) return;
    setUploading(true);
    setError(null);
    const form = new FormData();
    form.append("file", file);
    try {
      const result = await api<UploadResult>(`/merchant/${config.merchant_id}/catalog`, { method: "POST", body: form });
      setUpload(result);
      const catalog = await api<{ results: Product[] }>(`/catalog/search?merchant_id=${config.merchant_id}&category=skincare&limit=5`);
      setProducts(catalog.results);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "The catalog could not be uploaded.");
    } finally {
      setUploading(false);
      event.target.value = "";
    }
  };

  const publish = async () => {
    if (!config) return;
    setPublishing(true);
    setError(null);
    try {
      const next = await api<MerchantConfig>(`/merchant/${config.merchant_id}/config`, {
        method: "PUT",
        body: JSON.stringify({
          name: config.name,
          size: config.size,
          accent_color: config.accent_color,
          status: "published",
        }),
      });
      setConfig(next);
      setPublished(true);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "The agent could not be published.");
    } finally {
      setPublishing(false);
    }
  };

  const copy = async (kind: "snippet" | "url", value: string) => {
    await navigator.clipboard.writeText(value);
    setCopied(kind);
    window.setTimeout(() => setCopied(null), 1600);
  };

  if (!config) {
    // Without a key there is nothing to show: this page reads and writes one merchant's
    // private configuration and catalog, and the API will not serve either unauthenticated.
    return (
      <main className="admin-loading admin-gate">
        {merchantKey ? (
          <>
            <LoaderCircle className="spin" /> Loading Mysa Skin…
          </>
        ) : (
          <form
            className="admin-key-form"
            onSubmit={(event) => {
              event.preventDefault();
              const value = new FormData(event.currentTarget).get("key");
              const next = typeof value === "string" ? value.trim() : "";
              if (!next) return;
              setMerchantKey(next);
              setKey(next);
            }}
          >
            <h1>Merchant sign in</h1>
            <p>
              Paste your merchant API key. Local development writes it to
              <code> var/merchant-key.txt</code> when the database is seeded.
            </p>
            <input name="key" type="password" placeholder="mk_…" autoComplete="off" required />
            <button type="submit">Open store setup</button>
          </form>
        )}
        {error ? <p className="admin-key-error">{error}</p> : null}
      </main>
    );
  }

  const mappings = upload?.mappings ?? defaultMappings;
  const productCount = upload?.ingested ?? 6;
  const issueCount = upload?.skipped ?? 0;

  return (
    <div className="admin-shell">
      <header className="admin-header">
        <a className="sway-logo" href="/admin">Sway</a>
        <nav aria-label="Merchant navigation">
          <a className="active" href="#setup">Store setup</a>
          <a href="#preview">Preview</a>
        </nav>
        <a className="storefront-link" href={config.hosted_url}><span>{config.name}</span><ExternalLink size={15} /></a>
      </header>

      <main className="admin-layout">
        <section className="setup-column" id="setup">
          <header className="admin-title">
            <h1>Make your catalog conversational</h1>
            <p>One skincare agent, the same checkout, and two ways to go live.</p>
          </header>

          <section className="setup-section">
            <div className="section-number">1</div>
            <div className="section-content">
              <div className="section-heading"><Store size={20} /><h2>Your shop</h2></div>
              <div className="field-grid">
                <label>Merchant name<input value={config.name} onChange={(event) => setConfig({ ...config, name: event.target.value })} /></label>
                <label>Category<input value="Skincare" readOnly aria-readonly="true" /><small>Fixed for Phase 0</small></label>
                <label>Currency<span className="select-field">SGD <ChevronDown size={15} /></span></label>
                <label>Accent color<span className="color-field"><i style={{ background: config.accent_color }} /><input value={config.accent_color} onChange={(event) => setConfig({ ...config, accent_color: event.target.value })} /></span></label>
              </div>
              <fieldset className="size-control">
                <legend>Merchant setup</legend>
                <button type="button" className={config.size === "sme" ? "active" : ""} onClick={() => setConfig({ ...config, size: "sme" })}>Small business</button>
                <button type="button" className={config.size === "enterprise" ? "active" : ""} onClick={() => setConfig({ ...config, size: "enterprise" })}>Large retailer</button>
                <span>{config.size === "sme" ? "File upload and hosted storefront" : "Feed-ready configuration and embedded deployment"}</span>
              </fieldset>
            </div>
          </section>

          <section className="setup-section">
            <div className="section-number">2</div>
            <div className="section-content">
              <div className="section-heading"><FileSpreadsheet size={20} /><h2>Your catalog</h2></div>
              <label className={`dropzone ${uploading ? "is-uploading" : ""}`}>
                <input type="file" accept=".csv,.xlsx,.json" onChange={(event) => void uploadCatalog(event)} disabled={uploading} />
                {uploading ? <LoaderCircle className="spin" size={30} /> : <CloudUpload size={32} />}
                <span>{uploading ? "Validating every row…" : "Drag and drop your file here"}<small>CSV, XLSX or JSON · maximum 5 MB</small></span>
                <strong>{uploading ? "Working" : "Browse files"}</strong>
              </label>
              <div className="file-row">
                <FileSpreadsheet size={19} />
                <span>{upload?.source.filename ?? "mysa-products.xlsx"}<small>{upload ? `${upload.source.format.toUpperCase()} catalog` : "Seed catalog · ready to replace"}</small></span>
                <div><Check size={15} /> Catalog available</div>
                <label className="replace-file">Replace file<input type="file" accept=".csv,.xlsx,.json" onChange={(event) => void uploadCatalog(event)} /></label>
              </div>

              <div className="mapping-block">
                <div><strong>Auto-mapped columns</strong><button type="button">Edit mapping</button></div>
                <ul>{Object.entries(mappings).map(([target, source]) => <li key={target}><span>{source}</span><ArrowRight size={13} /><strong>{target.replace("_cents", "")}</strong></li>)}</ul>
              </div>

              <div className="validation-block">
                <header>
                  <strong>Validation summary</strong>
                  <span className="ready-count"><Check size={14} /> {productCount} products ready</span>
                  <span className={issueCount ? "issue-count" : "quiet-count"}><CircleAlert size={14} /> {issueCount} {issueCount === 1 ? "needs" : "need"} review</span>
                </header>
                {upload?.errors.length ? (
                  <table><thead><tr><th>Row</th><th>Issue</th><th>Result</th></tr></thead><tbody>{upload.errors.slice(0, 4).map((issue) => <tr key={`${issue.row}-${issue.reason}`}><td>{issue.row}</td><td>{issue.reason}</td><td>Skipped safely</td></tr>)}</tbody></table>
                ) : <div className="all-clear"><Check size={16} /> Required skincare facts, prices and stock are ready.</div>}
              </div>
            </div>
          </section>

          <section className="setup-section">
            <div className="section-number">3</div>
            <div className="section-content">
              <div className="section-heading"><Link2 size={20} /><h2>Go live</h2><span>Both options use the same catalog and checkout.</span></div>
              <div className="deployment-options">
                <article>
                  <h3>Website widget</h3><p>Embed the Sway assistant on your existing site.</p>
                  <div className="code-field"><code>{config.embed_snippet}</code><button type="button" onClick={() => void copy("snippet", config.embed_snippet)}><Clipboard size={15} /> {copied === "snippet" ? "Copied" : "Copy"}</button></div>
                  <span><LockKeyhole size={14} /> Sandboxed iframe · mobile responsive</span>
                </article>
                <article>
                  <h3>Hosted storefront</h3><p>Launch a ready-to-go storefront hosted by Sway.</p>
                  <div className="url-row"><code>{config.hosted_url}</code><button type="button" onClick={() => void copy("url", config.hosted_url)}><Clipboard size={15} /> {copied === "url" ? "Copied" : "Copy"}</button><a className="hosted-qr" href={config.hosted_url} aria-label="Open hosted storefront QR code"><QRCodeSVG value={config.hosted_url} size={52} level="M" /></a></div>
                  <span><Check size={14} /> Shareable · always up to date</span>
                </article>
              </div>
            </div>
          </section>

          {error ? <div className="inline-error" role="alert">{error}</div> : null}
          <footer className="publish-bar">
            <div>{published ? <Check size={18} /> : <RefreshCw size={18} />}<span><strong>{published ? "Your agent is live" : "Ready to publish"}</strong><small>{productCount} products ready · skincare pack active · simulated payments</small></span></div>
            <button type="button" onClick={() => void publish()} disabled={publishing}>{publishing ? "Publishing…" : published ? "Republish changes" : "Publish agent"}<ArrowRight size={17} /></button>
          </footer>
        </section>

        <aside className="live-preview" id="preview">
          <header><span>Live preview ({config.name} agent)</span><strong><i /> Connected</strong></header>
          <div className="preview-window">
            <div className="preview-top"><strong>Mysa Skin</strong><span>Your skincare, personalized.</span></div>
            <div className="preview-message"><i>M</i><span>Hi! I’m your skincare assistant. What does your skin need today?</span></div>
            <div className="preview-chips"><button>Dryness</button><button>Sensitive skin</button><button>Build a routine</button></div>
            <p>Top catalog matches</p>
            <div className="preview-products">
              {products.slice(0, 3).map((product) => <article key={product.sku}><img src={product.image_url ?? ""} alt="" /><strong>{product.title}</strong><span>{money(product.price_cents)}</span></article>)}
            </div>
            <div className="preview-composer">Ask anything about skincare… <ArrowRight size={16} /></div>
          </div>
          <a className="open-preview" href={config.hosted_url}><ExternalLink size={16} /> Open full hosted storefront</a>
          <p className="preview-security"><LockKeyhole size={15} /> Same grounded catalog, consent and checkout in both deployment modes.</p>
        </aside>
      </main>
    </div>
  );
}
