const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";

type RequestOptions = RequestInit & { idempotencyKey?: string };

export class ApiError extends Error {
  code: string;
  details: Record<string, unknown>;

  constructor(message: string, code = "REQUEST_FAILED", details = {}) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.details = details;
  }
}

/**
 * Credentials the API requires, held in one place so no call site has to remember them.
 *
 * - `sessionToken` proves this browser opened the shopping session it is driving.
 * - `consumerToken` identifies a signed-in shopper. Absent means browsing anonymously,
 *   which is allowed: the store works without an account until checkout needs an address.
 * - `merchantKey` authorises the admin page against one merchant.
 *
 * The consumer token and merchant key persist so a refresh does not sign you out; the
 * session token deliberately does not, because a session is per visit.
 */
const CONSUMER_TOKEN_KEY = "sway.consumerToken";
const MERCHANT_KEY_KEY = "sway.merchantKey";
const MERCHANT_STORES_KEY = "sway.merchantStores";

function readStored(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeStored(key: string, value: string | null): void {
  try {
    if (value === null) window.localStorage.removeItem(key);
    else window.localStorage.setItem(key, value);
  } catch {
    /* private browsing or blocked storage - the app still works for this visit */
  }
}

const credentials = {
  sessionToken: null as string | null,
  consumerToken: readStored(CONSUMER_TOKEN_KEY),
  merchantKey: readStored(MERCHANT_KEY_KEY),
};

export function setSessionToken(token: string | null): void {
  credentials.sessionToken = token;
}

export function setConsumerToken(token: string | null): void {
  credentials.consumerToken = token;
  writeStored(CONSUMER_TOKEN_KEY, token);
}

export function getConsumerToken(): string | null {
  return credentials.consumerToken;
}

export function setMerchantKey(key: string | null): void {
  credentials.merchantKey = key;
  writeStored(MERCHANT_KEY_KEY, key);
}

export function getMerchantKey(): string | null {
  return credentials.merchantKey;
}

/**
 * Stores this browser has opened before, most recent first.
 *
 * A merchant key is the only credential this product has, and it is shown exactly once. Every
 * merchant who signed up therefore had to keep a key in a text file and paste it back in to
 * return — which is a password prompt wearing a worse hat. Remembering the stores opened on
 * this machine turns coming back into one click.
 *
 * The keys live in this browser's localStorage, the same place the active key already lived,
 * and they never leave it. "Forget" removes one; signing out of a store does not, because
 * switching stores is the thing this list exists to make easy.
 */
export type RememberedStore = {
  merchant_id: string;
  name: string;
  key: string;
  last_opened: string;
};

export function rememberedStores(): RememberedStore[] {
  try {
    const raw = window.localStorage.getItem(MERCHANT_STORES_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter((entry): entry is RememberedStore => {
        const store = entry as Partial<RememberedStore>;
        return typeof store?.merchant_id === "string" && typeof store?.key === "string";
      })
      .sort((a, b) => (a.last_opened < b.last_opened ? 1 : -1));
  } catch {
    // Corrupt or blocked storage is an empty list, never a broken sign-in page.
    return [];
  }
}

function writeStores(stores: RememberedStore[]): void {
  try {
    window.localStorage.setItem(MERCHANT_STORES_KEY, JSON.stringify(stores.slice(0, 8)));
  } catch {
    /* private browsing - the current session still works, it just will not be remembered */
  }
}

export function rememberStore(store: { merchant_id: string; name: string; key: string }): void {
  const others = rememberedStores().filter((entry) => entry.merchant_id !== store.merchant_id);
  writeStores([{ ...store, last_opened: new Date().toISOString() }, ...others]);
}

export function forgetStore(merchantId: string): void {
  writeStores(rememberedStores().filter((entry) => entry.merchant_id !== merchantId));
}

export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { idempotencyKey, ...fetchOptions } = options;
  const isForm = fetchOptions.body instanceof FormData;
  const response = await fetch(`${API_BASE}${path}`, {
    ...fetchOptions,
    headers: {
      ...(isForm ? {} : { "Content-Type": "application/json" }),
      ...(idempotencyKey ? { "Idempotency-Key": idempotencyKey } : {}),
      ...(credentials.sessionToken ? { "X-Session-Token": credentials.sessionToken } : {}),
      ...(credentials.consumerToken ? { Authorization: `Bearer ${credentials.consumerToken}` } : {}),
      ...(credentials.merchantKey ? { "X-Merchant-Key": credentials.merchantKey } : {}),
      ...fetchOptions.headers,
    },
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = payload.detail?.error ?? payload.error ?? {};
    throw new ApiError(error.message ?? "The request could not be completed.", error.code, error.details);
  }
  return payload as T;
}

/**
 * Fetch an image the merchant owns but shoppers cannot see yet, as an object URL.
 *
 * A staged catalog's pictures are merchant-only until the store publishes, and an <img>
 * tag cannot send the merchant key - so the admin page fetches the bytes with credentials
 * and points the tag at the resulting blob. Callers must revokeObjectURL when done.
 */
export async function apiObjectUrl(path: string): Promise<string | null> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: credentials.merchantKey ? { "X-Merchant-Key": credentials.merchantKey } : {},
  });
  if (!response.ok) return null;
  return URL.createObjectURL(await response.blob());
}

export function money(cents: number, currency = "SGD"): string {
  return new Intl.NumberFormat("en-SG", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
  })
    .format(cents / 100)
    .replace("$", "S$");
}
