import { X } from "lucide-react";
import { money } from "../../api";
import type { Comparison } from "../../types";

type Props = {
  comparison: Comparison;
  onClose: () => void;
  onChoose: (sku: string) => void;
};

function displayValue(key: string, value: unknown): string {
  if (value === null || value === undefined || value === "") return "Not specified";
  if (key === "price_cents") return money(Number(value));
  if (key === "rating" && typeof value === "object") {
    const rating = value as { average: number | null; count: number | null };
    return rating.average === null ? "Not rated" : `${rating.average.toFixed(1)} · ${rating.count} ratings`;
  }
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (Array.isArray(value)) return value.join(", ");
  if (key === "size_ml") return `${value} ml`;
  return String(value);
}

export function ComparisonDrawer({ comparison, onClose, onChoose }: Props) {
  return (
    <section className="comparison-drawer" aria-label="Product comparison">
      <header>
        <div>
          <p>Verified comparison</p>
          <h2>Comparing {comparison.products.length} products</h2>
          <span>Built in code from current catalog rows · 0 model calls</span>
        </div>
        <button type="button" className="icon-button" onClick={onClose} aria-label="Close comparison">
          <X size={20} />
        </button>
      </header>
      <div className="comparison-scroll">
        <table>
          <thead>
            <tr>
              <th scope="col">Feature</th>
              {comparison.products.map((product) => (
                <th scope="col" key={product.sku}>
                  <span className="compare-product">
                    <img src={product.image_url ?? ""} alt="" />
                    {product.title}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {comparison.dimensions.map((dimension) => (
              <tr key={dimension.key}>
                <th scope="row">{dimension.label}</th>
                {dimension.cells.map((cell) => (
                  <td key={cell.sku}>{displayValue(dimension.key, cell.value)}</td>
                ))}
              </tr>
            ))}
            <tr>
              <th scope="row">Choose</th>
              {comparison.products.map((product) => (
                <td key={product.sku}>
                  <button type="button" className="table-action" onClick={() => onChoose(product.sku)}>
                    Choose {product.title}
                  </button>
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  );
}

