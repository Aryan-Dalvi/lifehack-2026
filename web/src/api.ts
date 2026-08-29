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

export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { idempotencyKey, ...fetchOptions } = options;
  const isForm = fetchOptions.body instanceof FormData;
  const response = await fetch(`${API_BASE}${path}`, {
    ...fetchOptions,
    headers: {
      ...(isForm ? {} : { "Content-Type": "application/json" }),
      ...(idempotencyKey ? { "Idempotency-Key": idempotencyKey } : {}),
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

export function money(cents: number, currency = "SGD"): string {
  return new Intl.NumberFormat("en-SG", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
  })
    .format(cents / 100)
    .replace("$", "S$");
}

