import { ArrowRight, Check, ChevronDown, CircleAlert, Clipboard, CloudUpload, Download, ExternalLink, FileSpreadsheet, Image as ImageIcon, Images, Link2, LoaderCircle, LockKeyhole, LogOut, RefreshCw, Sparkles, Store, TriangleAlert, Upload } from "lucide-react";
import { QRCodeSVG } from "qrcode.react";
import { type ChangeEvent, type FormEvent, useEffect, useState } from "react";
import { api, getMerchantKey, money, rememberStore, setMerchantKey } from "../../api";
import { MerchantGate } from "./MerchantGate";
import { MERCHANT_ACCENT_PRESETS, isValidAccent, merchantThemeStyle, normalizeAccent } from "../../theme";
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
  logo_url: string | null;
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

const UNSAVED_KEY_STORAGE = "sway.unsavedMerchantKey";

type UnsavedKey = { merchant_id: string; api_key: string };

/**
 * A newly created store's key, held until the merchant confirms they have saved it.
 *
 * Only the hash is stored server-side, so this really is the only copy. Keeping it across a
 * reload is the difference between "I closed the tab" and "I lost my store".
 */
function readUnsavedKey(): UnsavedKey | null {
  try {
    const raw = window.localStorage.getItem(UNSAVED_KEY_STORAGE);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<UnsavedKey>;
    return typeof parsed?.merchant_id === "string" && typeof parsed?.api_key === "string"
      ? { merchant_id: parsed.merchant_id, api_key: parsed.api_key }
      : null;
  } catch {
    return null;
  }
}

function writeUnsavedKey(value: UnsavedKey | null): void {
  try {
    if (value) window.localStorage.setItem(UNSAVED_KEY_STORAGE, JSON.stringify(value));
    else window.localStorage.removeItem(UNSAVED_KEY_STORAGE);
  } catch {
    /* private browsing: the banner still shows for this visit, it just will not survive a reload */
  }
}

export function MerchantAdmin({ onNavigate }: { onNavigate?: (path: string) => void }) {
  const [config, setConfig] = useState<MerchantConfig | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [upload, setUpload] = useState<UploadResult | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadingImages, setUploadingImages] = useState(false);
  const [uploadingLogo, setUploadingLogo] = useState(false);
  const [imageReport, setImageReport] = useState<ImageReport | null>(null);
  const [loadingReview, setLoadingReview] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [published, setPublished] = useState(false);
  const [copied, setCopied] = useState<"snippet" | "url" | "key" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [merchantKey, setKey] = useState<string>(getMerchantKey() ?? "");
  const [creating, setCreating] = useState(false);
  // A key is shown exactly once, so a new store's key is pinned to the top of the page it
  // lands on and kept across reloads until the merchant says they have it. It used to be a
  // full-screen wall between creating a store and seeing it, which is a strange thing to
  // put in a 90-second onboarding.
  const [unsavedKey, setUnsavedKey] = useState<{ merchant_id: string; api_key: string } | null>(
    () => readUnsavedKey(),
  );

  useEffect(() => {
    // The key identifies the store - the page never assumes which merchant it is serving.
    // /merchant/me resolves the caller, then their catalog is read with their own id.
    // Deliberately does not clear the error: signing out *is* how a rejected key gets here,
    // and this effect re-runs as part of that. Clearing here wiped "that key opened nothing"
    // in the same tick it was set, so a bad key looked like nothing had happened at all.
    // The error is cleared when the merchant tries something new instead.
    if (!merchantKey) return;
    let cancelled = false;
    api<MerchantConfig>("/merchant/me")
      .then(async (merchant) => {
        if (cancelled) return;
        setConfig(merchant);
        setPublished(merchant.status === "published");
        // Only a key the server has just accepted is worth remembering, and only now do we
        // know the store's real name to label it with.
        rememberStore({ merchant_id: merchant.merchant_id, name: merchant.name, key: merchantKey });
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
    setError(null);
  };

  const openStore = (store: { merchant_id?: string; name?: string; key: string }) => {
    setError(null);
    setMerchantKey(store.key);
    setKey(store.key);
  };

  const createStore = async (name: string, size: "sme" | "enterprise") => {
    setCreating(true);
    setError(null);
    try {
      const created = await api<OnboardResult>("/merchant/onboard", {
        method: "POST",
        body: JSON.stringify({ name, size, category: "skincare" }),
      });
      // The key is returned exactly once - only its digest is stored. Rather than stop the
      // merchant at a screen to copy it, sign them straight in and carry the key with them
      // as a banner they dismiss when they have saved it.
      rememberStore({ merchant_id: created.merchant_id, name, key: created.api_key });
      writeUnsavedKey({ merchant_id: created.merchant_id, api_key: created.api_key });
      setUnsavedKey({ merchant_id: created.merchant_id, api_key: created.api_key });
      setMerchantKey(created.api_key);
      setKey(created.api_key);
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

  const uploadLogo = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file || !config) return;
    setUploadingLogo(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const result = await api<{ logo_url: string }>(`/merchant/${config.merchant_id}/logo`, {
        method: "POST",
        body: form,
      });
      setConfig({ ...config, logo_url: result.logo_url });
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "That logo could not be uploaded.");
    } finally {
      setUploadingLogo(false);
      event.target.value = "";
    }
  };

  const removeLogo = async () => {
    if (!config) return;
    setUploadingLogo(true);
    setError(null);
    try {
      await api(`/merchant/${config.merchant_id}/logo`, { method: "DELETE" });
      setConfig({ ...config, logo_url: null });
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "The logo could not be removed.");
    } finally {
      setUploadingLogo(false);
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

  const copy = async (kind: "snippet" | "url" | "key", value: string) => {
    await navigator.clipboard.writeText(value);
    setCopied(kind);
    window.setTimeout(() => setCopied(null), 1600);
  };

  if (!config) {
    // Without a key there is nothing to show: this page reads and writes one merchant's
    // private configuration and catalog, and the API will not serve either unauthenticated.
    if (merchantKey) {
      return (
        <main className="admin-loading gate-loading">
          <LoaderCircle className="spin" size={22} />
          <p>Opening your store…</p>
        </main>
      );
    }
    return (
      <MerchantGate
        busy={creating}
        creating={creating}
        error={error}
        onOpen={openStore}
        onCreate={(name, size) => void createStore(name, size)}
      />
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
  const accentValid = isValidAccent(config.accent_color);
  const publishBlocked = approvalBlocked || !accentValid;

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
        <button
          type="button"
          className="sign-out"
          onClick={signOut}
          title={config.merchant_id}
          aria-label="Switch store"
        >
          <LogOut size={14} /> <span>Switch store</span>
        </button>
      </header>

      {unsavedKey && unsavedKey.merchant_id === config.merchant_id ? (
        <aside className="key-banner" role="note">
          <div className="key-banner-copy">
            <p>Save your store key</p>
            <span>
              You are signed in already — this is the only time the key is shown. It is how you
              sign back in from another browser or machine.
            </span>
          </div>
          <code>{unsavedKey.api_key}</code>
          <button type="button" className="key-banner-copy-button" onClick={() => void copy("key", unsavedKey.api_key)}>
            <Clipboard size={14} /> {copied === "key" ? "Copied" : "Copy"}
          </button>
          <button
            type="button"
            className="key-banner-done"
            onClick={() => {
              writeUnsavedKey(null);
              setUnsavedKey(null);
            }}
          >
            I have saved it
          </button>
        </aside>
      ) : null}

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
                <label className="accent-control">Brand accent
                  <span className={`color-field ${accentValid ? "" : "is-invalid"}`}>
                    <input
                      className="color-picker"
                      type="color"
                      aria-label="Choose brand accent color"
                      value={normalizeAccent(config.accent_color)}
                      onChange={(event) => setConfig({ ...config, accent_color: event.target.value.toUpperCase() })}
                    />
                    <input
                      className="color-value"
                      aria-label="Brand accent hex value"
                      aria-invalid={!accentValid}
                      maxLength={7}
                      value={config.accent_color}
                      onChange={(event) => setConfig({ ...config, accent_color: event.target.value.toUpperCase() })}
                    />
                  </span>
                  <span className="color-presets" aria-label="Brand accent presets">
                    {MERCHANT_ACCENT_PRESETS.map((preset) => (
                      <button
                        key={preset.value}
                        type="button"
                        className={normalizeAccent(config.accent_color) === preset.value ? "active" : ""}
                        style={{ background: preset.value }}
                        aria-label={`Use ${preset.label} accent`}
                        title={preset.label}
                        onClick={() => setConfig({ ...config, accent_color: preset.value })}
                      />
                    ))}
                  </span>
                  {!accentValid ? <small className="color-error" role="alert">Use a six-digit colour such as #435744.</small> : null}
                </label>
              </div>
              <div className="logo-control">
                <span className="logo-control-label">Store logo</span>
                <div className="logo-row">
                  <div className={`logo-preview ${config.logo_url ? "" : "logo-preview--empty"}`}>
                    {config.logo_url ? (
                      <img src={config.logo_url} alt={`${config.name} logo`} />
                    ) : (
                      <ImageIcon size={20} />
                    )}
                  </div>
                  <div className="logo-actions">
                    <label className="logo-upload">
                      <input
                        type="file"
                        accept="image/png,image/jpeg,image/gif"
                        onChange={(event) => void uploadLogo(event)}
                        disabled={uploadingLogo}
                      />
                      {uploadingLogo ? <LoaderCircle className="spin" size={14} /> : <Upload size={14} />}
                      {config.logo_url ? "Replace logo" : "Upload logo"}
                    </label>
                    {config.logo_url ? (
                      <button type="button" className="text-link" onClick={() => void removeLogo()} disabled={uploadingLogo}>
                        Remove
                      </button>
                    ) : null}
                    <small>
                      PNG, JPEG or GIF up to 512 KB. Shown top left of your storefront in place of
                      your store name.
                    </small>
                  </div>
                </div>
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
              <a className="template-callout" href="/api/catalog/template" download>
                <span className="template-callout-icon"><Download size={22} /></span>
                <span>
                  <strong>Download the Excel template</strong>
                  <small>Recommended · includes every required skincare catalog column</small>
                </span>
                <ArrowRight size={19} />
              </a>
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
            <button type="button" onClick={() => void publish()} disabled={publishing || publishBlocked}>{publishing ? "Publishing…" : !accentValid ? "Choose a valid accent" : approvalBlocked ? "Complete catalog review" : published ? "Republish changes" : "Publish agent"}<ArrowRight size={17} /></button>
          </footer>
        </section>

        <aside className="live-preview" id="preview">
          <header><span>Live preview ({config.name} agent)</span><strong><i /> Connected</strong></header>
          <div className="preview-window" style={merchantThemeStyle(config.accent_color)}>
            <div className="preview-top">
              {config.logo_url ? (
                <img className="preview-logo" src={config.logo_url} alt={config.name} />
              ) : (
                <strong>{config.name}</strong>
              )}
              <span>Your skincare, personalized.</span>
            </div>
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
