import { Check, ShoppingBag, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { money } from "../../api";
import type { Product } from "../../types";

type Props = {
  product: Product;
  selected: boolean;
  disabled?: boolean;
  quantityInCart?: number;
  onToggleCompare: (sku: string) => void;
  onChoose: (sku: string) => void;
};

function attributeSummary(product: Product): Array<[string, string]> {
  const attributes = product.attributes;
  return [
    ["Best for", attributes.skin_types?.join(", ") ?? "See catalog"],
    ["Fragrance", attributes.fragrance_free ? "Fragrance-free" : "See ingredients"],
    ["Texture", attributes.texture ?? "Not specified"],
    ["Key ingredients", attributes.ingredients?.slice(0, 3).join(", ") ?? "See catalog"],
  ];
}

export function ProductCard({ product, selected, disabled, quantityInCart = 0, onToggleCompare, onChoose }: Props) {
  const atStockLimit = quantityInCart >= product.stock;
  const [previewOpen, setPreviewOpen] = useState(false);

  useEffect(() => {
    if (!previewOpen) return;
    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape") setPreviewOpen(false);
    };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [previewOpen]);

  return (
    <article
      className={`product-card ${selected ? "product-card--selected" : ""}`}
      tabIndex={0}
      aria-describedby={`${product.sku}-details`}
      onMouseEnter={() => setPreviewOpen(true)}
      onMouseLeave={() => setPreviewOpen(false)}
      onFocus={() => setPreviewOpen(true)}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) setPreviewOpen(false);
      }}
    >
      <button
        className="product-visual"
        type="button"
        aria-label={`Preview details for ${product.title}`}
        aria-expanded={previewOpen}
        onClick={() => setPreviewOpen((value) => !value)}
      >
        <img src={product.image_url ?? ""} alt="" loading="lazy" />
      </button>

      <div className="product-copy">
        <p className="product-step">{product.attributes.routine_step ?? "Skincare"}</p>
        <h3>{product.title}</h3>
        <strong className="product-price">{money(product.price_cents, product.currency)}</strong>
        {product.rating_avg !== null && product.rating_count !== null ? (
          <p className="rating" aria-label={`${product.rating_avg} out of 5 from ${product.rating_count} ratings`}>
            <span aria-hidden="true">★★★★★</span> {product.rating_avg.toFixed(1)} ({product.rating_count})
          </p>
        ) : (
          <p className="rating rating--empty">Not yet rated</p>
        )}
      </div>

      <div className="product-actions">
        <button
          type="button"
          className="text-action"
          disabled={disabled && !selected}
          onClick={() => onToggleCompare(product.sku)}
        >
          {selected ? <Check size={15} /> : <Sparkles size={15} />}
          {selected ? "Selected" : "Compare"}
        </button>
        <button
          type="button"
          className={`choose-action ${quantityInCart > 0 ? "choose-action--in-cart" : ""}`}
          disabled={atStockLimit}
          onClick={() => onChoose(product.sku)}
        >
          <ShoppingBag size={15} />
          {atStockLimit ? "Out of stock" : quantityInCart > 0 ? `In cart · ${quantityInCart}` : "Add to cart"}
        </button>
      </div>

      <div
        id={`${product.sku}-details`}
        className={`product-preview ${previewOpen ? "product-preview--open" : ""}`}
        aria-hidden={!previewOpen}
      >
        <p>Catalog details</p>
        <dl>
          {attributeSummary(product).map(([label, value]) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
        <span>4 key facts · compare for the full table</span>
      </div>
    </article>
  );
}

