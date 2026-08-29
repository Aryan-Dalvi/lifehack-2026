import { ArrowRight, Check, ChevronDown, CircleAlert, Clipboard, CloudUpload, ExternalLink, FileSpreadsheet, Link2, LoaderCircle, LockKeyhole, RefreshCw, Store } from "lucide-react";
import { QRCodeSVG } from "qrcode.react";
import { type ChangeEvent, useEffect, useState } from "react";
import { api, money } from "../../api";
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
  upload_id: string;
  status: "review_ready" | "published";
  preview_hash: string;
  approval_required: boolean;
  ready: number;
  ingested: number;
  skipped: number;
  errors: Array<{ row: number; reason: string; status: "review_required" | "rejected" }>;
  source: { filename: string; format: string; sha256: string; row_count: number };
  mappings: Record<string, string>;
  partial_success: boolean;
  summary: { input_rows: number; ready: number; review_required: number; rejected: number; fallback_rows: number };
  classifier: { source: string; model: string; prompt_hash: string };
  approval: {
    base_catalog_hash: string;
    reviewed_row_count_required: number;
    modes: Record<"replace" | "upsert", {
      allowed: boolean;
      blocked_reason: string | null;
      approval_token: string;
      publish_count: number;
      publish_skus: string[];
      removal_count: number;
      removal_skus: string[];
      held_count: number;
    }>;
  };
  pagination: { offset: number; limit: number; returned: number; total: number; next_offset: number | null };
  preview_truncated: boolean;
  products: Array<{
    row: number;
    status: "ready" | "review_required" | "rejected";
    canonical: { title: string; attributes: { product_type: string | null; categories: string[] } } | null;
    classification: {
      assignments: Array<{
        axis: string;
        proposed_label: string;
        is_primary: boolean;
        evidence: Array<{ column: string; raw_excerpt: string }>;
      }>;
    };
  }>;
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
  const [loadingReview, setLoadingReview] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [published, setPublished] = useState(false);
  const [copied, setCopied] = useState<"snippet" | "url" | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
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
  }, []);

  const uploadCatalog = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file || !config) return;
    setUploading(true);
    setError(null);
    const form = new FormData();
    form.append("file", file);
    try {
      const result = await api<UploadResult>(`/merchant/${config.merchant_id}/catalog/uploads`, { method: "POST", body: form });
      setUpload(result);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "The catalog could not be uploaded.");
    } finally {
      setUploading(false);
      event.target.value = "";
    }
  };

  const loadMoreReview = async () => {
    if (!config || !upload?.pagination.next_offset) return;
    setLoadingReview(true);
    setError(null);
    try {
      const nextPage = await api<UploadResult>(
        `/merchant/${config.merchant_id}/catalog/uploads/${upload.upload_id}?offset=${upload.pagination.next_offset}&limit=100`,
      );
      setUpload((current) => current ? {
        ...nextPage,
        products: [...current.products, ...nextPage.products],
        errors: [...current.errors, ...nextPage.errors],
      } : nextPage);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "The next review page could not be loaded.");
    } finally {
      setLoadingReview(false);
    }
  };

  const publish = async () => {
    if (!config) return;
    setPublishing(true);
    setError(null);
    try {
      if (upload?.approval_required) {
        const mode = upload.skipped ? "upsert" : "replace";
        const plan = upload.approval.modes[mode];
        if (upload.products.length !== upload.approval.reviewed_row_count_required) {
          throw new Error("Load and review every catalog row before publishing.");
        }
        if (!plan.allowed) throw new Error(plan.blocked_reason ?? "This approval plan is blocked.");
        await api(`/merchant/${config.merchant_id}/catalog/uploads/${upload.upload_id}/approve`, {
          method: "POST",
          body: JSON.stringify({
            approval_token: plan.approval_token,
            reviewed_row_count: upload.products.length,
            mode,
          }),
        });
        setUpload({ ...upload, status: "published", approval_required: false });
      }
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
      const catalog = await api<{ results: Product[] }>(`/catalog/search?merchant_id=${config.merchant_id}&category=skincare&limit=5`);
      setProducts(catalog.results);
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
    return <main className="admin-loading"><LoaderCircle className="spin" /> Loading Mysa Skin…</main>;
  }

  const mappings = upload?.mappings ?? defaultMappings;
  const productCount = upload?.ready ?? 6;
  const issueCount = upload?.skipped ?? 0;
  const reviewComplete = !upload || upload.products.length === upload.approval.reviewed_row_count_required;
  const publishMode = upload?.skipped ? "upsert" : "replace";
  const publishPlan = upload?.approval.modes[publishMode];
  const approvalBlocked = Boolean(upload?.approval_required && (!reviewComplete || !publishPlan?.allowed));

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
                <span>{uploading ? "Cleaning and categorizing every row…" : "Drag and drop your file here"}<small>CSV, XLSX or JSON · maximum 5 MB</small></span>
                <strong>{uploading ? "Working" : "Browse files"}</strong>
              </label>
              <div className="file-row">
                <FileSpreadsheet size={19} />
                <span>{upload?.source.filename ?? "mysa-products.xlsx"}<small>{upload ? `${upload.source.format.toUpperCase()} catalog` : "Seed catalog · ready to replace"}</small></span>
                <div><Check size={15} /> {upload?.approval_required ? "Preview ready" : "Catalog available"}</div>
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
                  <div className="review-table-scroll"><table><thead><tr><th>Row</th><th>Issue</th><th>Result</th></tr></thead><tbody>{upload.errors.map((issue) => <tr key={`${issue.row}-${issue.reason}`}><td>{issue.row}</td><td>{issue.reason}</td><td>Held from publish</td></tr>)}</tbody></table></div>
                ) : <div className="all-clear"><Check size={16} /> Every row was cleaned, categorized and grounded in merchant data.</div>}
                {upload ? <small>Classifier: {upload.classifier.source.replaceAll("_", " ")} ({upload.classifier.model}) · changes stay in preview until you approve and publish.</small> : null}
                {upload ? (
                  <div className="classification-preview">
                    <strong>Agent category preview · {upload.products.length}/{upload.pagination.total} rows reviewed</strong>
                    <div className="review-table-scroll"><table>
                        <thead><tr><th>Product</th><th>Proposed categories</th><th>Source evidence</th><th>Status</th></tr></thead>
                        <tbody>{upload.products.map((product) => {
                          const assignments = product.classification.assignments.filter((assignment) => assignment.axis === "product_type" || assignment.axis === "skin_type" || assignment.axis === "concern");
                          const evidence = assignments.flatMap((assignment) => assignment.evidence.map((item) => `${item.column}: “${item.raw_excerpt}”`));
                          return <tr key={product.row}><td>{product.canonical?.title ?? `Row ${product.row}`}</td><td>{assignments.map((assignment) => assignment.proposed_label).join(", ") || "Needs review"}</td><td>{evidence.slice(0, 2).join(" · ") || "No accepted evidence"}</td><td>{product.status.replace("_", " ")}</td></tr>;
                        })}</tbody>
                      </table></div>
                    {upload.pagination.next_offset !== null ? <button className="load-review" type="button" onClick={() => void loadMoreReview()} disabled={loadingReview}>{loadingReview ? "Loading…" : `Load next ${Math.min(100, upload.pagination.total - upload.products.length)} rows`}</button> : null}
                    <div className="approval-plan">
                      <strong>{publishMode === "replace" ? "Replacement plan" : "Safe partial update"}</strong>
                      <span>{publishMode === "replace"
                        ? `${publishPlan?.publish_count ?? 0} products will publish; ${publishPlan?.removal_count ?? 0} existing products will be removed${publishPlan?.removal_skus.length ? ` (${publishPlan.removal_skus.join(", ")})` : ""}.`
                        : `${publishPlan?.publish_count ?? 0} ready products will update or be added; ${publishPlan?.held_count ?? 0} held rows and every other live product remain unchanged.`}</span>
                      {!reviewComplete ? <small>Load every remaining page to enable approval.</small> : null}
                    </div>
                  </div>
                ) : null}
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
            <button type="button" onClick={() => void publish()} disabled={publishing || approvalBlocked}>{publishing ? "Publishing…" : approvalBlocked ? "Complete catalog review" : published ? "Republish changes" : "Publish agent"}<ArrowRight size={17} /></button>
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
