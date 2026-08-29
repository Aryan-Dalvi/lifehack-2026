import { ArrowRight, Sparkles, X } from "lucide-react";
import { useEffect } from "react";
import type { Product } from "../../types";
import { ProductCard } from "./ProductCard";

type Props = {
  products: Product[];
  selectedSkus: string[];
  basketSkus: Array<{ sku: string; quantity: number }>;
  busy: boolean;
  onClose: () => void;
  onToggleCompare: (sku: string) => void;
  onChoose: (sku: string) => void;
  onCompare: () => void;
};

export function ProductsModal({
  products,
  selectedSkus,
  basketSkus,
  busy,
  onClose,
  onToggleCompare,
  onChoose,
  onCompare,
}: Props) {
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  return (
    <div className="sheet-backdrop products-modal-backdrop" onClick={onClose} role="dialog" aria-modal="true">
      <div className="products-modal-content" onClick={(event) => event.stopPropagation()}>
        <header className="products-modal-header">
          <div>
            <p>Catalog options</p>
            <h2>All Grounded Products ({products.length})</h2>
          </div>
          <button
            type="button"
            className="icon-button"
            onClick={onClose}
            aria-label="Close products modal"
          >
            <X size={20} />
          </button>
        </header>

        <div className="products-modal-scroll">
          <div className="products-modal-grid">
            {products.map((product) => (
              <ProductCard
                key={product.sku}
                product={product}
                selected={selectedSkus.includes(product.sku)}
                disabled={selectedSkus.length >= 3}
                quantityInCart={basketSkus.find((line) => line.sku === product.sku)?.quantity ?? 0}
                onToggleCompare={onToggleCompare}
                onChoose={onChoose}
              />
            ))}
          </div>
        </div>

        {selectedSkus.length >= 2 ? (
          <footer className="products-modal-footer">
            <span>{selectedSkus.length} of 3 selected</span>
            <button
              type="button"
              className="compare-action"
              onClick={() => {
                onClose();
                onCompare();
              }}
              disabled={busy}
            >
              <Sparkles size={16} /> Compare {selectedSkus.length} products <ArrowRight size={16} />
            </button>
          </footer>
        ) : null}
      </div>
    </div>
  );
}
