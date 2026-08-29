import { ArrowRight, Layers3 } from "lucide-react";
import { money } from "../../api";
import type { CategoryTableData } from "../../types";

type Props = {
  data: CategoryTableData;
  busy: boolean;
  onSelect: (key: string) => void;
};

export function CategoryTable({ data, busy, onSelect }: Props) {
  return (
    <section className="category-browser" aria-labelledby="category-browser-title">
      <header>
        <div className="category-browser-icon"><Layers3 size={18} /></div>
        <div>
          <p>Skincare range</p>
          <h2 id="category-browser-title">Shop by category</h2>
          <span>Live availability from this merchant’s catalog · 0 model calls</span>
        </div>
      </header>
      <div className="category-table-scroll">
        <table aria-label="Available skincare categories">
          <thead>
            <tr><th>Category</th><th>What it helps with</th><th>Available</th><th>Starting at</th><th><span className="sr-only">Browse</span></th></tr>
          </thead>
          <tbody>
            {data.categories.map((category) => (
              <tr key={category.key}>
                <th scope="row">{category.label}</th>
                <td>{category.description}</td>
                <td>{category.product_count} {category.product_count === 1 ? "product" : "products"}</td>
                <td>{money(category.from_price_cents, category.currency)}</td>
                <td>
                  <button type="button" disabled={busy} onClick={() => onSelect(category.key)} aria-label={`Browse ${category.label}`}>
                    View <ArrowRight size={14} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
