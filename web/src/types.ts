export type ProductAttributes = {
  routine_step?: string;
  skin_types?: string[];
  concerns?: string[];
  ingredients?: string[];
  excludes?: string[];
  fragrance_free?: boolean | null;
  texture?: string;
  size_ml?: number;
};

export type Product = {
  sku: string;
  merchant_id: string;
  merchant_name: string;
  merchant_size: "sme" | "enterprise";
  title: string;
  description: string;
  price_cents: number;
  currency: string;
  image_url: string | null;
  category: "skincare";
  attributes: ProductAttributes;
  stock: number;
  rating_avg: number | null;
  rating_count: number | null;
  rating_source: string;
};

export type TurnEvent = {
  type: string;
  data: Record<string, unknown>;
};

export type Address = {
  address_id: string;
  recipient: string;
  lines: string[];
  postal_code: string;
  country: string;
};

export type CartPreview = {
  status: "preview";
  cart_id: string;
  cart_mandate_id: string;
  cart_hash: string;
  items: Array<{
    sku: string;
    title: string;
    quantity: number;
    unit_price_cents: number;
  }>;
  total_cents: number;
  currency: string;
  merchant: string;
  shipping_address: Address;
  card_brand: string;
  last4: string;
  card_expiry: string;
  receipt_email: string | null;
  expires_at: string;
  simulated: boolean;
};

export type Consent = {
  status: "confirmed";
  cart_id: string;
  cart_hash: string;
  amount_cents: number;
  currency: string;
  merchant_id: string;
  payment_mandate_id: string;
  token_id: string;
  message: string;
};

export type Receipt = {
  transaction_id: string;
  order_id: string;
  merchant: string;
  items: CartPreview["items"];
  total_cents: number;
  currency: string;
  card_brand: string;
  last4: string;
  auth_code: string;
  issuer: string;
  eci: string;
  at: string;
  simulated: boolean;
  email_delivery?: EmailDelivery;
};

export type TrustEvent = {
  seq: number;
  stage: string;
  label: string;
  status: "ok" | "warn" | "fail";
  detail: Record<string, unknown>;
};

export type RoutineStep = {
  step: string;
  label: string;
  order: number;
  when: string[];
  sku: string;
  title: string;
  advice: string | null;
  alternatives: number;
};

export type Routine = {
  steps: RoutineStep[];
  missing_steps: Array<{ step: string; label: string }>;
  usage_detail: boolean;
  plan_source: "catalog_database";
  phrasing_source: string;
};

export type Comparison = {
  products: Product[];
  dimensions: Array<{
    key: string;
    label: string;
    cells: Array<{ sku: string; value: unknown }>;
  }>;
  source: "catalog_database";
  llm_calls: 0;
};

export type CategoryGroup = {
  key: string;
  label: string;
  description: string;
  product_count: number;
  from_price_cents: number;
  currency: string;
};

export type CategoryTableData = {
  categories: CategoryGroup[];
  source: "catalog_database";
  llm_calls: 0;
};

export type EmailDelivery = {
  recipient: string | null;
  status: "sent" | "simulated" | "failed" | "skipped";
  channel: "smtp" | "demo_outbox" | "none";
};

export type SessionCard = {
  brand: string;
  last4: string;
  expiry: string;
  holder: string;
};

export type MerchantTheme = {
  name: string;
  accent_color: string;
  logo_url: string | null;
};

