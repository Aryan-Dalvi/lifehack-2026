import { Plus, RefreshCw, Save, X } from "lucide-react";
import {
  type ChangeEvent,
  type FormEvent,
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
} from "react";
import { api, money } from "../../api";

export type ManagedProduct = {
  sku: string;
  title: string;
  description: string;
  price_cents: number;
  currency: string;
  image_url: string | null;
  product_type: string | null;
  ingredients: string[];
  skin_types: string[];
  concerns: string[];
  stock: number;
};

export type ManagedProductList = {
  merchant_id: string;
  currency: string;
  total: number;
  products: ManagedProduct[];
};

export type ProductManagementProps = {
  merchantId: string;
  currency: string;
  /** Lets the dashboard refresh catalog KPIs after a successful create or update. */
  onCatalogChanged?: (products: ManagedProduct[]) => void;
};

type ProductDraft = {
  sku: string;
  title: string;
  description: string;
  price: string;
  stock: string;
  imageUrl: string;
  productType: string;
  ingredients: string;
  skinTypes: string;
  concerns: string;
};

type ProductPayload = {
  title: string;
  description: string;
  price_cents: number;
  stock: number;
  image_url: string | null;
  product_type: string | null;
  ingredients: string[];
  skin_types: string[];
  concerns: string[];
};

const EMPTY_DRAFT: ProductDraft = {
  sku: "",
  title: "",
  description: "",
  price: "",
  stock: "0",
  imageUrl: "",
  productType: "",
  ingredients: "",
  skinTypes: "",
  concerns: "",
};

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "The product could not be saved.";
}

function list(value: string): string[] {
  return [...new Set(value.split(",").map((item) => item.trim()).filter(Boolean))];
}

function productDraft(product: ManagedProduct): ProductDraft {
  return {
    sku: product.sku,
    title: product.title,
    description: product.description ?? "",
    price: (product.price_cents / 100).toFixed(2),
    stock: String(product.stock),
    imageUrl: product.image_url ?? "",
    productType: product.product_type ?? "",
    ingredients: product.ingredients.join(", "),
    skinTypes: product.skin_types.join(", "),
    concerns: product.concerns.join(", "),
  };
}

function payloadFor(draft: ProductDraft): ProductPayload {
  const title = draft.title.trim();
  if (!title) throw new Error("Enter a product name.");

  if (!/^\d+(?:\.\d{1,2})?$/.test(draft.price.trim())) {
    throw new Error("Enter a valid price with no more than two decimal places.");
  }
  const priceCents = Math.round(Number(draft.price) * 100);
  if (!Number.isSafeInteger(priceCents) || priceCents < 0) {
    throw new Error("Price must be zero or greater.");
  }

  if (!/^\d+$/.test(draft.stock.trim())) {
    throw new Error("Stock must be a whole number that is zero or greater.");
  }
  const stock = Number(draft.stock);
  if (!Number.isSafeInteger(stock)) throw new Error("Enter a smaller stock quantity.");

  return {
    title,
    description: draft.description.trim(),
    price_cents: priceCents,
    stock,
    image_url: draft.imageUrl.trim() || null,
    product_type: draft.productType.trim() || null,
    ingredients: list(draft.ingredients),
    skin_types: list(draft.skinTypes),
    concerns: list(draft.concerns),
  };
}

function fieldUpdater(
  setDraft: React.Dispatch<React.SetStateAction<ProductDraft>>,
  setStatus?: React.Dispatch<React.SetStateAction<string>>,
) {
  return (field: keyof ProductDraft) =>
    (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
      const value = event.target.value;
      setDraft((current) => ({ ...current, [field]: value }));
      setStatus?.("");
    };
}

function DetailFields({
  draft,
  setDraft,
  disabled,
  idPrefix,
  onChange,
}: {
  draft: ProductDraft;
  setDraft: React.Dispatch<React.SetStateAction<ProductDraft>>;
  disabled: boolean;
  idPrefix: string;
  onChange?: () => void;
}) {
  const update = fieldUpdater(setDraft);
  const change = (field: keyof ProductDraft) =>
    (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
      update(field)(event);
      onChange?.();
    };

  return (
    <div className="crm-product-details">
      <label className="crm-product-field crm-product-field--description" htmlFor={`${idPrefix}-description`}>
        <span>Description</span>
        <textarea
          id={`${idPrefix}-description`}
          rows={2}
          value={draft.description}
          onChange={change("description")}
          disabled={disabled}
          placeholder="What shoppers should know about this product"
        />
      </label>
      <label className="crm-product-field" htmlFor={`${idPrefix}-image`}>
        <span>Image URL</span>
        <input
          id={`${idPrefix}-image`}
          type="url"
          inputMode="url"
          value={draft.imageUrl}
          onChange={change("imageUrl")}
          disabled={disabled}
          placeholder="https://…"
        />
      </label>
      <label className="crm-product-field" htmlFor={`${idPrefix}-ingredients`}>
        <span>Ingredients</span>
        <input
          id={`${idPrefix}-ingredients`}
          value={draft.ingredients}
          onChange={change("ingredients")}
          disabled={disabled}
          placeholder="Comma-separated"
        />
      </label>
      <label className="crm-product-field" htmlFor={`${idPrefix}-skin-types`}>
        <span>Skin types</span>
        <input
          id={`${idPrefix}-skin-types`}
          value={draft.skinTypes}
          onChange={change("skinTypes")}
          disabled={disabled}
          placeholder="Dry, oily, sensitive"
        />
      </label>
      <label className="crm-product-field" htmlFor={`${idPrefix}-concerns`}>
        <span>Concerns</span>
        <input
          id={`${idPrefix}-concerns`}
          value={draft.concerns}
          onChange={change("concerns")}
          disabled={disabled}
          placeholder="Acne, redness, hydration"
        />
      </label>
    </div>
  );
}

function ProductEditorRow({
  merchantId,
  currency,
  product,
  onSaved,
}: {
  merchantId: string;
  currency: string;
  product: ManagedProduct;
  onSaved: (product: ManagedProduct) => void;
}) {
  const rawId = useId();
  const idPrefix = `product-${rawId.replace(/:/g, "")}`;
  const [draft, setDraft] = useState(() => productDraft(product));
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState("");
  const initial = useMemo(() => JSON.stringify(productDraft(product)), [product]);
  const dirty = JSON.stringify(draft) !== initial;
  const statusKind = status === "Saved" ? "saved" : status ? "error" : dirty ? "dirty" : "current";
  const update = fieldUpdater(setDraft, setStatus);

  useEffect(() => {
    setDraft(productDraft(product));
  }, [product]);

  async function save(event: FormEvent) {
    event.preventDefault();
    setStatus("");
    let payload: ProductPayload;
    try {
      payload = payloadFor(draft);
    } catch (error) {
      setStatus(errorMessage(error));
      return;
    }

    setSaving(true);
    try {
      const updated = await api<ManagedProduct>(
        `/merchant/${encodeURIComponent(merchantId)}/products/${encodeURIComponent(product.sku)}`,
        { method: "PUT", body: JSON.stringify(payload) },
      );
      onSaved(updated);
      setStatus("Saved");
    } catch (error) {
      setStatus(errorMessage(error));
    } finally {
      setSaving(false);
    }
  }

  return (
    <tbody className="crm-product-row-group">
      <tr>
        <td>
          <label className="crm-sr-only" htmlFor={`${idPrefix}-title`}>
            Product name for {product.sku}
          </label>
          <input
            className="crm-product-input crm-product-input--title"
            id={`${idPrefix}-title`}
            value={draft.title}
            onChange={update("title")}
            disabled={saving}
            required
          />
          <small>SKU {product.sku}</small>
        </td>
        <td>
          <label className="crm-sr-only" htmlFor={`${idPrefix}-price`}>
            Price for {draft.title || product.sku}
          </label>
          <div className="crm-product-money-input">
            <span aria-hidden>{currency === "SGD" ? "S$" : currency}</span>
            <input
              id={`${idPrefix}-price`}
              type="text"
              inputMode="decimal"
              value={draft.price}
              onChange={update("price")}
              disabled={saving}
              required
            />
          </div>
        </td>
        <td>
          <label className="crm-sr-only" htmlFor={`${idPrefix}-stock`}>
            Stock for {draft.title || product.sku}
          </label>
          <input
            className="crm-product-input crm-product-input--number"
            id={`${idPrefix}-stock`}
            type="number"
            inputMode="numeric"
            min="0"
            step="1"
            value={draft.stock}
            onChange={update("stock")}
            disabled={saving}
            required
          />
        </td>
        <td>
          <label className="crm-sr-only" htmlFor={`${idPrefix}-type`}>
            Product type for {draft.title || product.sku}
          </label>
          <input
            className="crm-product-input"
            id={`${idPrefix}-type`}
            value={draft.productType}
            onChange={update("productType")}
            disabled={saving}
            placeholder="e.g. Serum"
          />
        </td>
        <td
          className="crm-product-row-status"
          data-state={statusKind}
          role="status"
          aria-live={statusKind === "error" ? "assertive" : "polite"}
        >
          {status || (dirty ? "Unsaved changes" : "Up to date")}
        </td>
        <td>
          <button
            className="crm-product-save"
            type="submit"
            form={`${idPrefix}-form`}
            disabled={saving || !dirty}
          >
            {saving ? <RefreshCw className="is-spinning" size={14} aria-hidden /> : <Save size={14} aria-hidden />}
            {saving ? "Saving…" : "Save"}
          </button>
        </td>
      </tr>
      <tr className="crm-product-detail-row">
        <td colSpan={6}>
          <form id={`${idPrefix}-form`} onSubmit={save}>
            <DetailFields
              draft={draft}
              setDraft={setDraft}
              disabled={saving}
              idPrefix={idPrefix}
              onChange={() => setStatus("")}
            />
          </form>
        </td>
      </tr>
    </tbody>
  );
}

function NewProductForm({
  merchantId,
  currency,
  onCreated,
  onCancel,
}: {
  merchantId: string;
  currency: string;
  onCreated: (product: ManagedProduct) => void;
  onCancel: () => void;
}) {
  const rawId = useId();
  const idPrefix = `new-product-${rawId.replace(/:/g, "")}`;
  const titleRef = useRef<HTMLInputElement>(null);
  const [draft, setDraft] = useState<ProductDraft>(EMPTY_DRAFT);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState("");
  const update = fieldUpdater(setDraft, setStatus);

  useEffect(() => titleRef.current?.focus(), []);

  async function create(event: FormEvent) {
    event.preventDefault();
    const sku = draft.sku.trim();
    if (!sku) {
      setStatus("Enter a unique SKU.");
      return;
    }

    let payload: ProductPayload;
    try {
      payload = payloadFor(draft);
    } catch (error) {
      setStatus(errorMessage(error));
      return;
    }

    setSaving(true);
    setStatus("");
    try {
      const created = await api<ManagedProduct>(
        `/merchant/${encodeURIComponent(merchantId)}/products`,
        { method: "POST", body: JSON.stringify({ sku, ...payload }) },
      );
      onCreated(created);
    } catch (error) {
      setStatus(errorMessage(error));
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className="crm-product-create" onSubmit={create} aria-labelledby={`${idPrefix}-heading`}>
      <header>
        <div>
          <h3 id={`${idPrefix}-heading`}>Add a product</h3>
          <p>SKU cannot be changed after the product is created.</p>
        </div>
        <button type="button" className="crm-product-cancel" onClick={onCancel} disabled={saving}>
          <X size={14} aria-hidden /> Cancel
        </button>
      </header>
      <fieldset disabled={saving}>
        <div className="crm-product-create-core">
          <label className="crm-product-field" htmlFor={`${idPrefix}-sku`}>
            <span>SKU</span>
            <input
              id={`${idPrefix}-sku`}
              value={draft.sku}
              onChange={update("sku")}
              autoCapitalize="characters"
              required
            />
          </label>
          <label className="crm-product-field" htmlFor={`${idPrefix}-title`}>
            <span>Product name</span>
            <input
              ref={titleRef}
              id={`${idPrefix}-title`}
              value={draft.title}
              onChange={update("title")}
              required
            />
          </label>
          <label className="crm-product-field" htmlFor={`${idPrefix}-price`}>
            <span>Price ({currency})</span>
            <input
              id={`${idPrefix}-price`}
              type="text"
              inputMode="decimal"
              value={draft.price}
              onChange={update("price")}
              placeholder="0.00"
              required
            />
          </label>
          <label className="crm-product-field" htmlFor={`${idPrefix}-stock`}>
            <span>Stock</span>
            <input
              id={`${idPrefix}-stock`}
              type="number"
              inputMode="numeric"
              min="0"
              step="1"
              value={draft.stock}
              onChange={update("stock")}
              required
            />
          </label>
          <label className="crm-product-field" htmlFor={`${idPrefix}-type`}>
            <span>Product type</span>
            <input
              id={`${idPrefix}-type`}
              value={draft.productType}
              onChange={update("productType")}
              placeholder="e.g. Serum"
            />
          </label>
        </div>
        <DetailFields draft={draft} setDraft={setDraft} disabled={saving} idPrefix={idPrefix} onChange={() => setStatus("")} />
      </fieldset>
      <footer>
        <span className="crm-product-form-status" role="status" aria-live="assertive">
          {status}
        </span>
        <button className="crm-product-save" type="submit" disabled={saving}>
          {saving ? <RefreshCw className="is-spinning" size={14} aria-hidden /> : <Plus size={14} aria-hidden />}
          {saving ? "Adding…" : "Add product"}
        </button>
      </footer>
    </form>
  );
}

export function ProductManagement({ merchantId, currency, onCatalogChanged }: ProductManagementProps) {
  const [products, setProducts] = useState<ManagedProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [adding, setAdding] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError("");
    try {
      const response = await api<ManagedProductList>(
        `/merchant/${encodeURIComponent(merchantId)}/products`,
      );
      setProducts(response.products);
    } catch (error) {
      setLoadError(errorMessage(error));
    } finally {
      setLoading(false);
    }
  }, [merchantId]);

  useEffect(() => {
    void load();
  }, [load]);

  function replaceProduct(updated: ManagedProduct) {
    const next = products.map((product) => (product.sku === updated.sku ? updated : product));
    setProducts(next);
    onCatalogChanged?.(next);
  }

  function addProduct(created: ManagedProduct) {
    const next = [...products, created].sort((left, right) => left.title.localeCompare(right.title));
    setProducts(next);
    onCatalogChanged?.(next);
    setAdding(false);
  }

  return (
    <section
      className="crm-card crm-table-card crm-product-manager"
      id="product-management"
      aria-labelledby="product-management-heading"
      aria-busy={loading}
    >
      <header className="crm-table-head crm-product-manager-head">
        <div>
          <h2 id="product-management-heading">Catalog management</h2>
          <p>Edit product information here without changing the sales history below.</p>
        </div>
        <button className="crm-product-add" type="button" onClick={() => setAdding(true)} disabled={adding}>
          <Plus size={15} aria-hidden /> Add product
        </button>
      </header>

      {adding ? (
        <NewProductForm
          merchantId={merchantId}
          currency={currency}
          onCreated={addProduct}
          onCancel={() => setAdding(false)}
        />
      ) : null}

      {loadError ? (
        <div className="crm-product-load-error" role="alert">
          <span>{loadError}</span>
          <button type="button" onClick={() => void load()}>
            <RefreshCw size={14} aria-hidden /> Try again
          </button>
        </div>
      ) : loading ? (
        <p className="crm-empty" role="status">Loading products…</p>
      ) : products.length ? (
        <div className="crm-table-scroll">
          <table className="crm-table crm-product-table">
            <thead>
              <tr>
                <th>Product</th>
                <th>Price</th>
                <th>Stock</th>
                <th>Type</th>
                <th>Status</th>
                <th aria-label="Save product" />
              </tr>
            </thead>
            {products.map((product) => (
              <ProductEditorRow
                key={product.sku}
                merchantId={merchantId}
                currency={currency}
                product={product}
                onSaved={replaceProduct}
              />
            ))}
          </table>
        </div>
      ) : (
        <div className="crm-product-empty">
          <p>No products yet.</p>
          <button type="button" className="crm-product-add" onClick={() => setAdding(true)}>
            <Plus size={15} aria-hidden /> Add your first product
          </button>
        </div>
      )}

      {products.length ? (
        <p className="crm-product-count">
          {products.length} product{products.length === 1 ? "" : "s"} · Average price {money(Math.round(products.reduce((sum, product) => sum + product.price_cents, 0) / products.length), currency)}
        </p>
      ) : null}
    </section>
  );
}
