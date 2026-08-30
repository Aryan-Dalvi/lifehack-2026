import { Check, ShoppingBag, Sparkles, X } from "lucide-react";
import { useEffect } from "react";
import { money } from "../../api";
import type { Product } from "../../types";

type Props = {
  product: Product;
  selected: boolean;
  quantityInCart: number;
  onClose: () => void;
  onToggleCompare: (sku: string) => void;
  onChoose: (sku: string) => void;
};

function facts(product: Product): Array<[string, string]> {
  const attributes = product.attributes;
  return [
    ["Routine step", attributes.routine_step ?? "Skincare"],
    ["Best for", attributes.skin_types?.join(", ") || "See product description"],
    ["Concerns", attributes.concerns?.join(", ") || "Not specified"],
    ["Key ingredients", attributes.ingredients?.join(", ") || "Not specified"],
    ["Fragrance", attributes.fragrance_free ? "Fragrance-free" : "Check the ingredient list"],
    ["Texture", attributes.texture ?? "Not specified"],
    ["Size", attributes.size_ml ? `${attributes.size_ml} ml` : "Not specified"],
  ];
}

export function ProductDetailModal({ product, selected, quantityInCart, onClose, onToggleCompare, onChoose }: Props) {
  useEffect(() => {
    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [onClose]);

  const atStockLimit = quantityInCart >= product.stock;
  return (
    <div className="sheet-backdrop product-detail-backdrop" role="presentation" onClick={onClose}>
      <section className="product-detail-sheet" role="dialog" aria-modal="true" aria-labelledby="product-detail-title" onClick={(event) => event.stopPropagation()}>
        <button type="button" className="icon-button product-detail-close" onClick={onClose} aria-label="Close product details"><X size={20} /></button>
        <div className="product-detail-image"><img src={product.image_url ?? ""} alt="" /></div>
        <div className="product-detail-copy">
          <p>Catalog-verified product</p>
          <h2 id="product-detail-title">{product.title}</h2>
          <strong>{money(product.price_cents, product.currency)}</strong>
          <span>{product.description || "No product description was supplied by the merchant."}</span>
          <dl>
            {facts(product).map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}
          </dl>
          <p className="product-detail-stock">{product.stock} in stock · {product.rating_avg === null ? "Not yet rated" : `${product.rating_avg.toFixed(1)} from ${product.rating_count} ratings`}</p>
          <div className="product-detail-actions">
            <button type="button" className="text-action" onClick={() => onToggleCompare(product.sku)}>
              {selected ? <Check size={16} /> : <Sparkles size={16} />} {selected ? "Selected to compare" : "Add to comparison"}
            </button>
            <button type="button" className="primary-action" disabled={atStockLimit} onClick={() => onChoose(product.sku)}>
              <ShoppingBag size={16} /> {atStockLimit ? "Stock limit reached" : quantityInCart ? `Add another · ${quantityInCart} in cart` : "Add to cart"}
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
