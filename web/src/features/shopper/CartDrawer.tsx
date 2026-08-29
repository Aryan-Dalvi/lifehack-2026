import { Minus, Plus, ShoppingBag, Trash2, X } from "lucide-react";
import { money } from "../../api";
import type { Product } from "../../types";

export type BasketLine = { product: Product; quantity: number };

type Props = {
  lines: BasketLine[];
  busy: boolean;
  onIncrement: (sku: string) => void;
  onDecrement: (sku: string) => void;
  onRemove: (sku: string) => void;
  onCheckout: () => void;
  onClose: () => void;
};

export function CartDrawer({ lines, busy, onIncrement, onDecrement, onRemove, onCheckout, onClose }: Props) {
  const totalCents = lines.reduce((sum, line) => sum + line.product.price_cents * line.quantity, 0);
  const currency = lines[0]?.product.currency ?? "SGD";

  return (
    <form
      className="cart-drawer"
      onSubmit={(event) => {
        event.preventDefault();
        onCheckout();
      }}
    >
      <header>
        <p>Your cart</p>
        <button type="button" className="icon-button" onClick={onClose} aria-label="Close cart"><X size={18} /></button>
      </header>

      {lines.length === 0 ? (
        <p className="cart-empty">Add a product to start a cart.</p>
      ) : (
        <ul className="cart-lines">
          {lines.map((line) => (
            <li key={line.product.sku}>
              <img src={line.product.image_url ?? ""} alt="" loading="lazy" />
              <div className="cart-line-copy">
                <strong>{line.product.title}</strong>
                <span>{money(line.product.price_cents, line.product.currency)}</span>
              </div>
              <div className="cart-line-qty">
                <button type="button" aria-label={`Remove one ${line.product.title}`} onClick={() => onDecrement(line.product.sku)}><Minus size={13} /></button>
                <span>{line.quantity}</span>
                <button
                  type="button"
                  aria-label={`Add one more ${line.product.title}`}
                  disabled={line.quantity >= line.product.stock}
                  onClick={() => onIncrement(line.product.sku)}
                >
                  <Plus size={13} />
                </button>
              </div>
              <button type="button" className="cart-line-remove" aria-label={`Remove ${line.product.title} from cart`} onClick={() => onRemove(line.product.sku)}>
                <Trash2 size={15} />
              </button>
            </li>
          ))}
        </ul>
      )}

      {lines.length > 0 ? (
        <>
          <div className="cart-total-row"><span>Total</span><strong>{money(totalCents, currency)}</strong></div>
          <button type="submit" className="primary-button cart-checkout" disabled={busy}>
            <ShoppingBag size={16} /> {busy ? "Preparing preview…" : "Checkout"}
          </button>
        </>
      ) : null}
    </form>
  );
}
