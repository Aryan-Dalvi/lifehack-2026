/**
 * The shapes `GET /merchant/{id}/insights` and its summary endpoint return.
 *
 * Kept beside the dashboard rather than in the shared `types.ts`: nothing else reads a CRM
 * figure, and the storefront and admin surfaces are edited in parallel by different people.
 */

export type Kpi = {
  key: string;
  label: string;
  value: number;
  display: string;
  previous: number;
  previous_display: string;
  change: number;
  change_percent: number | null;
  delta_display: string;
  direction: "up" | "down" | "flat";
  is_good: boolean;
  unit: "count" | "money";
};

export type RevenuePoint = {
  date: string;
  label: string;
  actual_cents: number | null;
  projected_cents: number | null;
  is_forecast: boolean;
};

export type Task = {
  code: string;
  title: string;
  detail: string;
  chip: string;
  severity: number;
  action: string;
  value_cents?: number;
  progress: { done: number; total: number; noun: string } | null;
};

export type CustomerRow = {
  consumer_id: string;
  name: string;
  handle: string;
  initials: string;
  is_anonymous: boolean;
  orders: number;
  spend_cents: number;
  open_cart_cents: number;
  value_cents: number;
  value_kind: string;
  note: string;
  last_item: string | null;
  last_activity_label: string;
  status: string;
  status_label: string;
};

export type Insights = {
  version: string;
  generated_at: string;
  merchant: {
    merchant_id: string;
    name: string;
    currency: string;
    status: "draft" | "published";
    accent_color: string;
    size: "sme" | "enterprise";
  };
  window: { days: number; start: string; end: string; previous_start: string; label: string };
  kpis: Kpi[];
  revenue_series: {
    currency: string;
    points: RevenuePoint[];
    actual_days: number;
    forecast_days: number;
    peak: RevenuePoint | null;
    forecast: {
      method: string;
      source: string;
      per_day_cents: number;
      horizon_days: number;
      total_cents: number;
    };
    max_cents: number;
  };
  insight: { text: string; source: string };
  tasks: Task[];
  customers: CustomerRow[];
  customer_tabs: Array<{ key: string; label: string; count: number }>;
  scorecards: Array<{ key: string; label: string; display: string; basis: string; hint: string }>;
  top_products: Array<{ sku: string; title: string; units: number; revenue_cents: number }>;
  catalog: {
    product_count: number;
    out_of_stock: string[];
    low_stock: string[];
    without_photo: string[];
    in_stock_count: number;
    with_photo_count: number;
    average_price_cents: number;
  };
  activity: {
    sessions: number;
    sessions_previous: number;
    signed_in_sessions: number;
    abandoned_carts: number;
    abandoned_cents: number;
  };
  payments: { mode: string; note: string };
};

export type Summary = {
  version: string;
  scope: string;
  title: string;
  question: string | null;
  summary: string;
  bullets: string[];
  source: string;
  window: string;
  generated_at: string;
};
