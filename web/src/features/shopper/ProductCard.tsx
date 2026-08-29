import { Check, ShoppingBag, Sparkles } from "lucide-react";
import { money } from "../../api";
import type { Product } from "../../types";

type Props = {
  product: Product;
  selected: boolean;
  disabled?: boolean;
  quantityInCart?: number;
  onToggleCompare: (sku: string) => void;
  onChoose: (sku: string) => void;
  onOpenDetails: (product: Product) => void;
};

export function ProductCard({ product, selected, disabled, quantityInCart = 0, onToggleCompare, onChoose, onOpenDetails }: Props) {
  const atStockLimit = quantityInCart >= product.stock;

  return (
    <article
      className={`product-card ${selected ? "product-card--selected" : ""}`}
      tabIndex={0}
      aria-label={`View details for ${product.title}`}
      onClick={(event) => {
        if (!(event.target as HTMLElement).closest("button")) onOpenDetails(product);
      }}
      onKeyDown={(event) => {
        if (event.target === event.currentTarget && (event.key === "Enter" || event.key === " ")) {
          event.preventDefault();
          onOpenDetails(product);
        }
      }}
    >
      <button
        className="product-visual"
        type="button"
        aria-label={`View details for ${product.title}`}
        onClick={() => onOpenDetails(product)}
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

    </article>
  );
}

