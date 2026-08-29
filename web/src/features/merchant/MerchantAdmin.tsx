import { ArrowRight, Check, ChevronDown, CircleAlert, Clipboard, CloudUpload, Download, ExternalLink, FileSpreadsheet, Images, Link2, LoaderCircle, LockKeyhole, LogOut, RefreshCw, Sparkles, Store, TriangleAlert } from "lucide-react";
import { QRCodeSVG } from "qrcode.react";
import { type ChangeEvent, type FormEvent, useEffect, useState } from "react";
import { api, getMerchantKey, money, setMerchantKey } from "../../api";
import { StagedImage } from "./StagedImage";
import type { Product } from "../../types";

type ImageReport = {
  archive: string;
  match_source: string;
  image_count: number;
  matched_count: number;
  product_count: number;
  unmatched_images: string[];
  products_without_images: string[];
  skipped_entries: Array<{ entry: string; reason: string }>;
  images: Array<{
    image_id?: string;
    entry_name: string;
    url: string | null;
    matched: boolean;
    sku?: string;
    title?: string;
    method?: string;
    confidence?: number;
    reason?: string;
  }>;
};

type OnboardResult = {
  merchant_id: string;
  api_key: string;
  hosted_url: string;
  embed_snippet: string;
};

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
  mapping_report: {
    source: string;
    decisions: Array<{ target: string; column: string; method: string; reason: string }>;
    unresolved: Array<{ target: string; candidate_columns: string[]; reason: string }>;
    ignored_columns: string[];
  };
  diagnostics: {
    headline: string;
    source: string;
    notes: string[];
    groups: Array<{
      code: string;
      title: string;
      why: string;
      fix: string;
      row_count: number;
      example_rows: number[];
      blocking: boolean;
    }>;
  };
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
    canonical: {
      sku: string;
      title: string;
      image_url: string | null;
      attributes: {
        product_type: string | null;
        categories: string[];
        catalog_cleaning: { image_source?: string; image_match?: { entry_name: string; method: string; confidence: number } };
      };
    } | null;
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

export function MerchantAdmin({ onNavigate }: { onNavigate?: (path: string) => void }) {
  const [config, setConfig] = useState<MerchantConfig | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [upload, setUpload] = useState<UploadResult | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadingImages, setUploadingImages] = useState(false);
  const [imageReport, setImageReport] = useState<ImageReport | null>(null);
  const [loadingReview, setLoadingReview] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [published, setPublished] = useState(false);
  const [copied, setCopied] = useState<"snippet" | "url" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [merchantKey, setKey] = useState<string>(getMerchantKey() ?? "");
  const [creating, setCreating] = useState(false);
  const [newStore, setNewStore] = useState<OnboardResult | null>(null);

  useEffect(() => {
    // The key identifies the store - the page never assumes which merchant it is serving.
    // /merchant/me resolves the caller, then their catalog is read with their own id.
    if (!merchantKey) {
      setError(null);
      return;
    }
    setError(null);
    let cancelled = false;
    api<MerchantConfig>("/merchant/me")
      .then(async (merchant) => {
        if (cancelled) return;
        setConfig(merchant);
        setPublished(merchant.status === "published");
        const catalog = await api<{ results: Product[] }>(
          `/catalog/search?merchant_id=${encodeURIComponent(merchant.merchant_id)}&category=skincare&limit=5`,
        );
        if (!cancelled) setProducts(catalog.results);
      })
      .catch((requestError: Error) => {
        if (cancelled) return;
        // A key that resolves to nobody is a signed-out state, not a broken page.
        setMerchantKey(null);
        setKey("");
        setError(requestError.message);
      });
    return () => {
      cancelled = true;
    };
  }, [merchantKey]);

  const signOut = () => {
    setMerchantKey(null);
    setKey("");
    setConfig(null);
    setUpload(null);
    setImageReport(null);
    setProducts([]);
    setNewStore(null);
    setError(null);
  };

  const createStore = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const name = String(form.get("name") ?? "").trim();
    if (!name) return;
    setCreating(true);
    setError(null);
    try {
      const created = await api<OnboardResult>("/merchant/onboard", {
        method: "POST",
        body: JSON.stringify({ name, size: String(form.get("size") ?? "sme"), category: "skincare" }),
      });
      // The key is returned exactly once - only its digest is stored - so it is shown to
      // the merchant before anything else happens, and kept for this browser.
      setNewStore(created);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "The store could not be created.");
    } finally {
      setCreating(false);
    }
  };

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

  const uploadImages = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file || !config) return;
    setUploadingImages(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      // Photos apply to the live catalog straight away, so this needs no staged upload and
      // no approval - refresh the product strip to show what actually changed.
      setImageReport(await api<ImageReport>(`/merchant/${config.merchant_id}/catalog/images`, { method: "POST", body: form }));
      const catalog = await api<{ results: Product[] }>(`/catalog/search?merchant_id=${config.merchant_id}&category=skincare&limit=5`);
      setProducts(catalog.results);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "The photo archive could not be read.");
    } finally {
      setUploadingImages(false);
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
      // Onboarding is finished the moment the agent is live: hand the merchant their CRM
      // dashboard rather than leaving them on a setup form they have no more use for.
      onNavigate?.("/admin");
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

  if (newStore) {
    // The key is shown once, before the dashboard, because this response is its only copy.
    return (
      <main className="admin-loading admin-gate">
        <div className="admin-key-form admin-new-store">
          <h1>Your store is ready</h1>
          <p>
            Save this API key now. It is shown once - only its hash is stored, so it cannot be
            shown again. It is how you sign back in to this store.
          </p>
          <code className="new-store-key">{newStore.api_key}</code>
          <button type="button" onClick={() => void navigator.clipboard.writeText(newStore.api_key)}>
            <Clipboard size={14} /> Copy key
          </button>
          <p className="new-store-id">Store id <code>{newStore.merchant_id}</code></p>
          <button
            type="button"
            className="primary"
            onClick={() => {
              setMerchantKey(newStore.api_key);
              setKey(newStore.api_key);
              setNewStore(null);
            }}
          >
            I have saved it - open store setup <ArrowRight size={14} />
          </button>
        </div>
      </main>
    );
  }

  if (!config) {
    // Without a key there is nothing to show: this page reads and writes one merchant's
    // private configuration and catalog, and the API will not serve either unauthenticated.
    return (
      <main className="admin-loading admin-gate">
        {merchantKey ? (
          <>
            <LoaderCircle className="spin" /> Opening your store…
          </>
        ) : (
          <div className="admin-gate-forms">
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
              <p>Paste your merchant API key. It identifies your store - there is nothing else to enter.</p>
              <input name="key" type="password" placeholder="mk_…" autoComplete="off" required />
              <button type="submit">Open store setup</button>
            </form>

            <form className="admin-key-form admin-signup" onSubmit={(event) => void createStore(event)}>
              <h1>New here?</h1>
              <p>Create a store and get your API key. Every merchant gets their own catalog, agent and storefront.</p>
              <input name="name" type="text" placeholder="Your store name" maxLength={100} required />
              <select name="size" defaultValue="sme">
                <option value="sme">Small business</option>
                <option value="enterprise">Large retailer</option>
              </select>
              <button type="submit" disabled={creating}>
                {creating ? <><LoaderCircle className="spin" size={14} /> Creating…</> : <>Create my store</>}
              </button>
            </form>
          </div>
        )}
        {error ? <p className="admin-key-error">{error}</p> : null}
      </main>
    );
  }

  const mappings = upload?.mappings ?? {};
  const diagnostics = upload?.diagnostics;
  const productCount = upload?.ready ?? products.length;
  const issueCount = upload?.skipped ?? 0;
  const reviewComplete = !upload || upload.products.length === upload.approval.reviewed_row_count_required;
  const publishMode = upload?.skipped ? "upsert" : "replace";
  const publishPlan = upload?.approval.modes[publishMode];
  const approvalBlocked = Boolean(upload?.approval_required && (!reviewComplete || !publishPlan?.allowed));

  return (
    <div className="admin-shell">
      <header className="admin-header">
        <a className="sway-logo" href="/admin/setup">Sway</a>
        <nav aria-label="Merchant navigation">
          <a href="/admin" onClick={(event) => { if (onNavigate) { event.preventDefault(); onNavigate("/admin"); } }}>Dashboard</a>
          <a className="active" href="#setup">Store setup</a>
          <a href="#preview">Preview</a>
        </nav>
        <a className="storefront-link" href={config.hosted_url}><span>{config.name}</span><ExternalLink size={15} /></a>
        <button type="button" className="sign-out" onClick={signOut} title={config.merchant_id}>
          <LogOut size={14} /> Switch store
        </button>
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
              <div className="section-heading">
                <FileSpreadsheet size={20} /><h2>Your catalog</h2>
                <a className="template-link" href="/api/catalog/template" download>
                  <Download size={14} /> Download the Excel template
                </a>
              </div>
              <label className={`dropzone ${uploading ? "is-uploading" : ""}`}>
                <input type="file" accept=".csv,.xlsx,.json" onChange={(event) => void uploadCatalog(event)} disabled={uploading} />
                {uploading ? <LoaderCircle className="spin" size={30} /> : <CloudUpload size={32} />}
                <span>{uploading ? "Cleaning and categorizing every row…" : "Drag and drop your file here"}<small>CSV, XLSX or JSON · maximum 5 MB</small></span>
                <strong>{uploading ? "Working" : "Browse files"}</strong>
              </label>
              <div className="file-row">
                <FileSpreadsheet size={19} />
                <span>{upload?.source.filename ?? (products.length ? "Your live catalog" : "No catalog yet")}<small>{upload ? `${upload.source.format.toUpperCase()} catalog` : products.length ? `${products.length} product${products.length === 1 ? "" : "s"} live · ready to replace` : "Upload a file to get started"}</small></span>
                <div>{upload?.approval_required ? <><Check size={15} /> Preview ready</> : products.length ? <><Check size={15} /> Catalog available</> : <><CircleAlert size={15} /> Empty</>}</div>
                <label className="replace-file">{products.length ? "Replace file" : "Choose file"}<input type="file" accept=".csv,.xlsx,.json" onChange={(event) => void uploadCatalog(event)} /></label>
              </div>

              <label className={`dropzone dropzone--images ${uploadingImages ? "is-uploading" : ""}`}>
                <input type="file" accept=".zip" onChange={(event) => void uploadImages(event)} disabled={uploadingImages} />
                {uploadingImages ? <LoaderCircle className="spin" size={26} /> : <Images size={28} />}
                <span>
                  {uploadingImages ? "Matching photos to your products…" : "Add a ZIP of product photos"}
                  <small>Applies to your live catalog right away · name each file after the product or its SKU · PNG, JPEG, WebP or GIF · maximum 25 MB</small>
                </span>
                <strong>{uploadingImages ? "Working" : "Browse ZIP"}</strong>
              </label>

              {imageReport ? (
                <div className="image-report">
                  <header>
                    <strong>{imageReport.archive}</strong>
                    <span className="ready-count"><Check size={14} /> {imageReport.matched_count} of {imageReport.image_count} photos matched</span>
                    {imageReport.match_source?.startsWith("hybrid") ? <span className="ai-badge"><Sparkles size={12} /> Assistant matched some names</span> : null}
                  </header>
                  <div className="image-strip">
                    {(imageReport.images ?? []).map((image) => (
                      <figure key={image.entry_name} className={image.matched ? "" : "is-unmatched"}>
                        <StagedImage src={image.url} alt={image.entry_name} />
                        <figcaption>
                          {image.matched ? image.title ?? image.sku : image.entry_name}
                          <small>{image.matched ? `${image.sku} · ${image.method?.replaceAll("_", " ")}` : "No product matched"}</small>
                        </figcaption>
                      </figure>
                    ))}
                  </div>
                  {imageReport.products_without_images?.length ? <small>Still without a photo: {imageReport.products_without_images.join(", ")}.</small> : null}
                                    {imageReport.skipped_entries?.length ? <small>Skipped {imageReport.skipped_entries.length} file{imageReport.skipped_entries.length === 1 ? "" : "s"}: {imageReport.skipped_entries.slice(0, 3).map((entry) => `${entry.entry} (${entry.reason})`).join("; ")}.</small> : null}
                </div>
              ) : null}

              {Object.keys(mappings).length ? (
              <div className="mapping-block">
                <div><strong>Mapped columns</strong></div>
                <ul>{Object.entries(mappings).map(([target, source]) => (
                  <li key={target}><span>{source}</span><ArrowRight size={13} /><strong>{target.replace("_cents", "")}</strong></li>
                ))}</ul>
                {upload?.mapping_report.ignored_columns.length ? (
                  <small>Not recognised, so skipped: {upload.mapping_report.ignored_columns.join(", ")}. Rename a column to match the template if it holds product detail.</small>
                ) : null}
              </div>
              ) : null}

              {diagnostics && (diagnostics.groups.length || diagnostics.notes.length) ? (
                <div className="diagnostics-block">
                  <header>
                    <TriangleAlert size={15} />
                    <strong>{diagnostics.headline}</strong>
                    {diagnostics.source.startsWith("model") ? <span className="ai-badge"><Sparkles size={12} /> Explained by the assistant</span> : null}
                  </header>
                  {diagnostics.groups.map((group) => (
                    <article key={group.code} className={group.blocking ? "is-blocking" : ""}>
                      <h4>{group.title}<span>{group.row_count} row{group.row_count === 1 ? "" : "s"}</span></h4>
                      <p>{group.why}</p>
                      <p className="fix"><strong>Fix:</strong> {group.fix}</p>
                      <small>For example row{group.example_rows.length === 1 ? "" : "s"} {group.example_rows.join(", ")}.</small>
                    </article>
                  ))}
                  {diagnostics.notes.map((note) => <small key={note} className="diagnostics-note">{note}</small>)}
                </div>
              ) : null}

              <div className="validation-block">
                <header>
                  <strong>Validation summary</strong>
                  <span className="ready-count"><Check size={14} /> {productCount} products ready</span>
                  <span className={issueCount ? "issue-count" : "quiet-count"}><CircleAlert size={14} /> {issueCount} {issueCount === 1 ? "needs" : "need"} review</span>
                </header>
                {upload?.errors.length ? (
                  <div className="review-table-scroll"><table><thead><tr><th>Row</th><th>Issue</th><th>Result</th></tr></thead><tbody>{upload.errors.map((issue) => <tr key={`${issue.row}-${issue.reason}`}><td>{issue.row}</td><td>{issue.reason}</td><td>Held from publish</td></tr>)}</tbody></table></div>
                ) : upload ? <div className="all-clear"><Check size={16} /> Every row was cleaned, categorized and grounded in merchant data.</div> : <div className="all-clear all-clear--empty"><CircleAlert size={16} /> Upload a catalog to see it cleaned, categorized and checked.</div>}
                {upload ? <small>Classifier: {upload.classifier.source.replaceAll("_", " ")} ({upload.classifier.model}) · changes stay in preview until you approve and publish.</small> : null}
                {upload ? (
                  <div className="classification-preview">
                    <strong>Agent category preview · {upload.products.length}/{upload.pagination.total} rows reviewed</strong>
                    <div className="review-table-scroll"><table>
                        <thead><tr><th>Photo</th><th>Product</th><th>Proposed categories</th><th>Source evidence</th><th>Status</th></tr></thead>
                        <tbody>{upload.products.map((product) => {
                          const assignments = product.classification.assignments.filter((assignment) => assignment.axis === "product_type" || assignment.axis === "skin_type" || assignment.axis === "concern");
                          const evidence = assignments.flatMap((assignment) => assignment.evidence.map((item) => `${item.column}: “${item.raw_excerpt}”`));
                          return <tr key={product.row}><td><StagedImage src={product.canonical?.image_url ?? null} alt="" /></td><td>{product.canonical?.title ?? `Row ${product.row}`}</td><td>{assignments.map((assignment) => assignment.proposed_label).join(", ") || "Needs review"}</td><td>{evidence.slice(0, 2).join(" · ") || "No accepted evidence"}</td><td>{product.status.replace("_", " ")}</td></tr>;
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
            <div className="preview-top"><strong>{config.name}</strong><span>Your skincare, personalized.</span></div>
            <div className="preview-message"><i>{config.name.trim().charAt(0).toUpperCase()}</i><span>Hi! I’m your skincare assistant. What does your skin need today?</span></div>
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
