import { ArrowRight, CircleDollarSign, LayoutGrid, LoaderCircle, Send, ShieldCheck, ShoppingBag, Sparkles, X } from "lucide-react";
import { type FormEvent, type ReactNode, useCallback, useEffect, useRef, useState } from "react";
import { ApiError, api, money, setSessionToken } from "../../api";
import { DEFAULT_MERCHANT_ACCENT, merchantThemeStyle } from "../../theme";
import type {
  CartPreview,
  CategoryTableData,
  Comparison,
  Consent,
  MerchantTheme,
  Product,
  Receipt,
  Routine,
  SessionCard,
  TrustEvent,
  TurnEvent,
} from "../../types";
import { type Account, AccountMenu } from "./AccountMenu";
import { AddressPrompt } from "./AddressPrompt";
import { CardPrompt } from "./CardPrompt";
import type { BasketLine } from "./CartDrawer";
import { CartSidebar } from "./CartSidebar";
import { CategoryTable } from "./CategoryTable";
import { BankSheet, ConsentSheet, ReceiptCard } from "./CheckoutSheets";
import { ComparisonDrawer } from "./ComparisonDrawer";
import { ProductCard } from "./ProductCard";
import { ProductDetailModal } from "./ProductDetailModal";
import { ProductsModal } from "./ProductsModal";
import { RoutinePlan } from "./RoutinePlan";
import type { JourneyStage } from "./TrustRail";

/** An assistant turn can carry the cards for the products its own sentence names. */
type ChatMessage = { id: string; role: "assistant" | "shopper"; text: string; products?: Product[] };
type Decline = {
  decline_code: string;
  reason: string;
  total_cents?: number;
  cap_cents?: number;
};
const initialMessage: ChatMessage = {
  id: "welcome",
  role: "assistant",
  text: "I can help you find gentle, catalog-verified skincare. What is your main concern right now, and is your skin easily sensitive?",
};

function newMessage(role: ChatMessage["role"], text: string): ChatMessage {
  return { id: crypto.randomUUID(), role, text };
}

/**
 * Assistant prose with every product it names set in bold.
 *
 * The agent only ever names products the Guardian verified against the catalog, so a bold
 * run is a promise: that product exists, at the price on the card shown beside the message.
 * Matching is done by scan rather than by regular expression, because a product title is
 * merchant-authored text and may contain anything. Longer titles win at the same position,
 * so "Mysa Gentle Cleanser" is never broken up by "Gentle Cleanser".
 */
function MessageText({ text, titles }: { text: string; titles: string[] }): ReactNode {
  const usable = titles.filter((title) => title.length > 3).sort((a, b) => b.length - a.length);
  if (usable.length === 0) return text;
  const haystack = text.toLowerCase();
  const nodes: ReactNode[] = [];
  let cursor = 0;
  let key = 0;
  while (cursor < text.length) {
    let hit: { at: number; length: number } | null = null;
    for (const title of usable) {
      const at = haystack.indexOf(title.toLowerCase(), cursor);
      if (at === -1) continue;
      if (hit === null || at < hit.at || (at === hit.at && title.length > hit.length)) {
        hit = { at, length: title.length };
      }
    }
    if (hit === null) break;
    if (hit.at > cursor) nodes.push(text.slice(cursor, hit.at));
    nodes.push(
      <strong key={key++} className="named-product">
        {text.slice(hit.at, hit.at + hit.length)}
      </strong>,
    );
    cursor = hit.at + hit.length;
  }
  if (cursor < text.length) nodes.push(text.slice(cursor));
  return nodes;
}

export function ShopperApp() {
  const params = new URLSearchParams(window.location.search);
  const merchantId = params.get("merchant") ?? "m_mysa";
  const embedded = params.get("embedded") === "1";
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([initialMessage]);
  const [products, setProducts] = useState<Product[]>([]);
  const [selectedSkus, setSelectedSkus] = useState<string[]>([]);
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [categories, setCategories] = useState<CategoryTableData | null>(null);
  // Cards for products the agent named in its own answer sit under that message; the
  // results rail below is for a shop-wide search, and showing both would say it twice.
  const [productsInline, setProductsInline] = useState(false);
  const [detailProduct, setDetailProduct] = useState<Product | null>(null);
  const [routine, setRoutine] = useState<Routine | null>(null);
  const [basket, setBasket] = useState<BasketLine[]>([]);
  const [productsModalOpen, setProductsModalOpen] = useState(false);
  const [cart, setCart] = useState<CartPreview | null>(null);
  const [consent, setConsent] = useState<Consent | null>(null);
  const [receipt, setReceipt] = useState<Receipt | null>(null);
  const [decline, setDecline] = useState<Decline | null>(null);
  const [stage, setStage] = useState<JourneyStage>("start");
  const [trustEvents, setTrustEvents] = useState<TrustEvent[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [limitOpen, setLimitOpen] = useState(false);
  const [limitDraft, setLimitDraft] = useState("");
  const [budgetCents, setBudgetCents] = useState<number | null>(null);
  const [bankChallengeId, setBankChallengeId] = useState<string | null>(null);
  const [bankOpen, setBankOpen] = useState(false);
  const [account, setAccount] = useState<Account | null>(null);
  const [anonymous, setAnonymous] = useState(true);
  const [bankError, setBankError] = useState<string | null>(null);
  const [addressPromptOpen, setAddressPromptOpen] = useState(false);
  const [addressError, setAddressError] = useState<string | null>(null);
  const [addressBusy, setAddressBusy] = useState(false);
  const [cardPromptOpen, setCardPromptOpen] = useState(false);
  const [cardError, setCardError] = useState<string | null>(null);
  const [cardBusy, setCardBusy] = useState(false);
  const [receiptEmail, setReceiptEmail] = useState("");
  const [emailError, setEmailError] = useState<string | null>(null);
  // Empty until the session says whose shop this is: a placeholder name here is another
  // merchant's brand on the screen, however briefly.
  const [merchantTheme, setMerchantTheme] = useState<MerchantTheme>({
    name: "",
    accent_color: DEFAULT_MERCHANT_ACCENT,
    logo_url: null,
  });
  const idempotencyKey = useRef(crypto.randomUUID());
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, products, routine, decline, comparison, categories, receipt, busy]);

  // Escape pressed inside an embedded storefront never reaches the page hosting it, so the
  // widget's own launcher could not be closed from the chat. Tell the host instead — after
  // this app's own dialogs have had their chance at the key.
  useEffect(() => {
    if (!embedded) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      if (document.querySelector(".sheet-backdrop")) return;
      // The host page's origin is by definition unknown — it is any merchant's site. The
      // message carries no data, and the widget verifies both the origin and the frame it
      // came from before acting on it.
      window.parent?.postMessage({ type: "sway:close" }, "*");
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [embedded]);

  const loadTrust = useCallback(async (activeSessionId: string) => {
    const payload = await api<{ events: TrustEvent[] }>(`/trust/events/snapshot?session_id=${encodeURIComponent(activeSessionId)}`);
    setTrustEvents(payload.events);
  }, []);

  useEffect(() => {
    let active = true;
    // Identity is never sent in the body: the server reads it from the consumer token, or
    // treats the session as anonymous.
    setSessionToken(null);
    api<{ session_id: string; session_token: string; greeting: string; anonymous: boolean; merchant: MerchantTheme }>(
      "/agent/session",
      {
        method: "POST",
        body: JSON.stringify({ merchant_id: merchantId, category: "skincare", budget_cents: null }),
      },
    )
      .then((payload) => {
        if (!active) return;
        // Must be set before any other call: every session-scoped endpoint requires it.
        setSessionToken(payload.session_token);
        setSessionId(payload.session_id);
        setAnonymous(payload.anonymous);
        setMerchantTheme(payload.merchant);
        return loadTrust(payload.session_id);
      })
      .catch((requestError: Error) => active && setError(requestError.message));
    return () => {
      active = false;
    };
  }, [loadTrust, merchantId]);

  // Signing in mid-visit attaches the account to the session already in progress rather
  // than opening a new one, so a basket built as a guest survives reaching the till.
  const onAccountChange = useCallback(
    (next: Account | null) => {
      setAccount(next);
      if (next?.email) setReceiptEmail((current) => current || next.email);
      if (!next || !sessionId) return;
      api<{ anonymous: boolean }>(`/agent/session/${sessionId}/identity`, { method: "PUT" })
        .then((payload) => setAnonymous(payload.anonymous))
        .catch((requestError: Error) => setError(requestError.message));
    },
    [sessionId],
  );

  const applyEvents = (events: TurnEvent[], suppressToken = false) => {
    // A turn either produces a routine or it does not; never carry a stale plan forward.
    let nextRoutine: Routine | null = null;
    // Cards the agent's own answer named. They are attached to that message rather than
    // pushed into the rail, so the sentence and the product it refers to stay together.
    let inlineProducts: Product[] | null = null;
    for (const event of events) {
      if (event.type === "routine") {
        nextRoutine = event.data as unknown as Routine;
      }
      if (!suppressToken && event.type === "token" && typeof event.data.text === "string") {
        setMessages((current) => [...current, newMessage("assistant", event.data.text as string)]);
      }
      if ((event.type === "clarification" || event.type === "safety_boundary") && typeof event.data.message === "string") {
        setMessages((current) => [...current, newMessage("assistant", event.data.message as string)]);
      }
      if (event.type === "product_cards") {
        const nextProducts = event.data.products as Product[];
        const inline = event.data.inline === true;
        setProducts(nextProducts);
        setProductsInline(inline);
        setSelectedSkus([]);
        setComparison(null);
        setCategories(null);
        setStage("products");
        if (inline) inlineProducts = nextProducts;
      }
      // Asking to compare in the chat gets the same verified table as the compare button.
      if (event.type === "comparison") {
        setComparison(event.data as unknown as Comparison);
        setCategories(null);
        setStage("comparison");
      }
      if (event.type === "category_table") {
        // A table with no rows is a header and a shrug. The agent says so in words instead,
        // so drop the empty one rather than drawing an empty frame around nothing.
        const table = event.data as unknown as CategoryTableData;
        setCategories(table.categories.length > 0 ? table : null);
        setComparison(null);
      }
    }
    if (inlineProducts) {
      const cards = inlineProducts;
      setMessages((current) => {
        const lastAssistant = [...current].reverse().find((message) => message.role === "assistant");
        if (!lastAssistant) return current;
        return current.map((message) =>
          message.id === lastAssistant.id ? { ...message, products: cards } : message,
        );
      });
    }
    setRoutine(nextRoutine);
  };

  const sendText = async (
    text: string,
    options: { showShopperMessage?: boolean; suppressToken?: boolean } = {},
  ) => {
    const trimmed = text.trim();
    if (!trimmed || !sessionId || busy) return;
    setBusy(true);
    setError(null);
    if (options.showShopperMessage !== false) {
      setMessages((current) => [...current, newMessage("shopper", trimmed)]);
    }
    setInput("");
    try {
      const response = await api<{ events: TurnEvent[] }>("/agent/turn", {
        method: "POST",
        body: JSON.stringify({ session_id: sessionId, text: trimmed }),
      });
      applyEvents(response.events, options.suppressToken);
      await loadTrust(sessionId);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "The request could not be completed.");
    } finally {
      setBusy(false);
    }
  };

  const submitMessage = (event: FormEvent) => {
    event.preventDefault();
    void sendText(input);
  };

  const toggleCompare = (sku: string) => {
    setSelectedSkus((current) => {
      if (current.includes(sku)) return current.filter((value) => value !== sku);
      if (current.length >= 3) return current;
      return [...current, sku];
    });
  };

  const compareProducts = async () => {
    if (!sessionId || selectedSkus.length < 2) return;
    setBusy(true);
    setError(null);
    try {
      const response = await api<{ type: "comparison"; data: Comparison }>("/agent/action", {
        method: "POST",
        body: JSON.stringify({ session_id: sessionId, action: "compare", skus: selectedSkus }),
      });
      setComparison(response.data);
      setStage("comparison");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Comparison could not be created.");
    } finally {
      setBusy(false);
    }
  };

  const browseCategory = async (routineStep: string) => {
    if (!sessionId || busy) return;
    setBusy(true);
    setError(null);
    try {
      const response = await api<{ type: "product_cards"; data: { products: Product[] } }>("/agent/action", {
        method: "POST",
        body: JSON.stringify({ session_id: sessionId, action: "browse_category", routine_step: routineStep }),
      });
      setProducts(response.data.products);
      setProductsInline(false);
      setSelectedSkus([]);
      setComparison(null);
      setCategories(null);
      setStage("products");
      await loadTrust(sessionId);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "That category could not be opened.");
    } finally {
      setBusy(false);
    }
  };

  const findProduct = (sku: string): Product | undefined =>
    products.find((product) => product.sku === sku) ??
    comparison?.products.find((product) => product.sku === sku) ??
    messages.flatMap((message) => message.products ?? []).find((product) => product.sku === sku);

  // Every product title the shopper has been shown, so the agent's prose can point at them.
  const knownTitles = Array.from(
    new Set([
      ...products.map((product) => product.title),
      ...(comparison?.products ?? []).map((product) => product.title),
      ...messages.flatMap((message) => (message.products ?? []).map((product) => product.title)),
      ...(routine?.steps ?? []).map((step) => step.title),
    ]),
  );

  const addToBasket = (sku: string) => {
    const product = findProduct(sku);
    if (!product) return;
    setBasket((current) => {
      const existing = current.find((line) => line.product.sku === sku);
      if (existing) {
        if (existing.quantity >= product.stock) return current;
        return current.map((line) => (line.product.sku === sku ? { ...line, quantity: line.quantity + 1 } : line));
      }
      return [...current, { product, quantity: 1 }];
    });
  };

  const incrementBasketLine = (sku: string) => {
    setBasket((current) =>
      current.map((line) => (line.product.sku === sku && line.quantity < line.product.stock ? { ...line, quantity: line.quantity + 1 } : line)),
    );
  };

  const decrementBasketLine = (sku: string) => {
    setBasket((current) =>
      current.flatMap((line) => {
        if (line.product.sku !== sku) return [line];
        if (line.quantity <= 1) return [];
        return [{ ...line, quantity: line.quantity - 1 }];
      }),
    );
  };

  const removeBasketLine = (sku: string) => {
    setBasket((current) => current.filter((line) => line.product.sku !== sku));
  };

  const startCheckout = async () => {
    if (!sessionId || busy || basket.length === 0) return;
    setBusy(true);
    setError(null);
    setDecline(null);
    try {
      const response = await api<{ type: "cart"; data: CartPreview | (Decline & { status: "declined" }) }>("/agent/action", {
        method: "POST",
        body: JSON.stringify({
          session_id: sessionId,
          action: "select",
          items: basket.map((line) => ({ sku: line.product.sku, quantity: line.quantity })),
        }),
      });
      if (response.data.status === "declined") {
        setDecline(response.data);
        setCart(null);
        setStage("declined");
      } else {
        const preview = response.data as CartPreview;
        setCart(preview);
        if (preview.receipt_email) setReceiptEmail((current) => current || (preview.receipt_email ?? ""));
        setStage("preview");
      }
      await loadTrust(sessionId);
    } catch (requestError) {
      if (requestError instanceof ApiError && requestError.code === "ADDRESS_REQUIRED") {
        setAddressPromptOpen(true);
      } else if (requestError instanceof ApiError && requestError.code === "CARD_REQUIRED") {
        setCardError(null);
        setCardPromptOpen(true);
      } else {
        setError(requestError instanceof Error ? requestError.message : "The transaction preview could not be created.");
      }
    } finally {
      setBusy(false);
    }
  };

  const submitCard = async (details: {
    number: string;
    expiry_month: number;
    expiry_year: number;
    cvc: string;
    holder: string;
  }) => {
    if (!sessionId) return;
    setCardBusy(true);
    setCardError(null);
    try {
      await api<SessionCard>(`/agent/session/${sessionId}/card`, {
        method: "PUT",
        body: JSON.stringify(details),
      });
      setCardPromptOpen(false);
      await loadTrust(sessionId);
      // The card was asked for because checkout needed it — carry on where it stopped.
      await startCheckout();
    } catch (requestError) {
      setCardError(requestError instanceof Error ? requestError.message : "That card could not be used.");
    } finally {
      setCardBusy(false);
    }
  };

  const submitAddress = async (address: { recipient: string; lines: string[]; postal_code: string; country: string }) => {
    if (!account) return;
    setAddressBusy(true);
    setAddressError(null);
    try {
      await api(`/consumer/${account.consumer_id}/addresses`, {
        method: "POST",
        body: JSON.stringify(address),
      });
      setAddressPromptOpen(false);
      await startCheckout();
    } catch (requestError) {
      setAddressError(
        requestError instanceof ApiError ? requestError.message : "The address could not be saved.",
      );
    } finally {
      setAddressBusy(false);
    }
  };

  const saveLimit = async (event: FormEvent) => {
    event.preventDefault();
    if (!sessionId) return;
    const dollars = Number(limitDraft);
    if (!Number.isFinite(dollars) || dollars <= 0) {
      setError("Enter a spending limit greater than S$0.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api(`/agent/session/${sessionId}/limit`, {
        method: "PUT",
        body: JSON.stringify({ budget_cents: Math.round(dollars * 100), currency: "SGD", source: "shopper_ui" }),
      });
      setBudgetCents(Math.round(dollars * 100));
      setCart(null);
      setConsent(null);
      setReceipt(null);
      setDecline(null);
      setLimitOpen(false);
      setMessages((current) => [...current, newMessage("assistant", `Your S$${dollars.toFixed(2)} spending limit is active. You can change or clear it at any time.`)]);
      await loadTrust(sessionId);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "The spending limit could not be updated.");
    } finally {
      setBusy(false);
    }
  };

  const clearLimit = async () => {
    if (!sessionId) return;
    setBusy(true);
    try {
      await api(`/agent/session/${sessionId}/limit`, {
        method: "PUT",
        body: JSON.stringify({ budget_cents: null, currency: "SGD", source: "shopper_ui" }),
      });
      setBudgetCents(null);
      setLimitDraft("");
      setLimitOpen(false);
      setCart(null);
      setConsent(null);
      setDecline(null);
      await loadTrust(sessionId);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "The spending limit could not be cleared.");
    } finally {
      setBusy(false);
    }
  };

  const confirmCart = async () => {
    if (!sessionId || !cart || busy) return;
    // An emailed receipt is the shopper's own copy of what the agent did, so the address is
    // checked here rather than after the money has moved.
    const trimmedEmail = receiptEmail.trim();
    if (trimmedEmail && !/^[^@\s]+@[^@\s.]+(\.[^@\s.]+)+$/.test(trimmedEmail)) {
      setEmailError("Check this address — the receipt is sent here.");
      return;
    }
    setEmailError(null);
    setBusy(true);
    setError(null);
    try {
      const confirmed = await api<Consent>("/agent/confirm", {
        method: "POST",
        body: JSON.stringify({
          session_id: sessionId,
          cart_id: cart.cart_id,
          confirmation: { method: "click" },
          receipt_email: trimmedEmail || null,
        }),
      });
      setConsent(confirmed);
      setStage("consented");
      const challenge = await api<{ challenge_id: string }>("/bank/challenge", {
        method: "POST",
        body: JSON.stringify({
          consumer_id: account?.consumer_id ?? "usr_demo",
          cart_hash: confirmed.cart_hash,
          amount_cents: confirmed.amount_cents,
          currency: confirmed.currency,
          merchant_id: confirmed.merchant_id,
          session_id: sessionId,
        }),
      });
      setBankChallengeId(challenge.challenge_id);
      setCart(null);
      setBankOpen(true);
      await loadTrust(sessionId);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Confirmation could not be recorded.");
    } finally {
      setBusy(false);
    }
  };

  const verifyBank = async (code: string) => {
    if (!sessionId || !bankChallengeId || !consent || busy) return;
    setBusy(true);
    setBankError(null);
    try {
      const verification = await api<{ status: string; bank_token?: string; decline_code?: string }>("/bank/verify", {
        method: "POST",
        body: JSON.stringify({ challenge_id: bankChallengeId, code, session_id: sessionId }),
      });
      if (verification.status !== "approved" || !verification.bank_token) {
        setBankError("That code was not accepted. Check it and try again.");
        return;
      }
      setStage("bank");
      const payment = await api<{ status: string; receipt?: Receipt; decline_code?: string; reason?: string }>("/agent/pay", {
        method: "POST",
        idempotencyKey: idempotencyKey.current,
        body: JSON.stringify({
          session_id: sessionId,
          cart_id: consent.cart_id,
          payment_mandate_id: consent.payment_mandate_id,
          token_id: consent.token_id,
          bank_token: verification.bank_token,
        }),
      });
      if (payment.status !== "approved" || !payment.receipt) {
        setDecline({ decline_code: payment.decline_code ?? "PAYMENT_DECLINED", reason: payment.reason ?? "The payment was not authorized." });
        setStage("declined");
      } else {
        setReceipt(payment.receipt);
        setBasket([]);
        setMessages((current) => [...current, newMessage("assistant", "Your order is confirmed. The receipt and verification evidence are shown below.")]);
        setStage("paid");
      }
      setBankOpen(false);
      await loadTrust(sessionId);
    } catch (requestError) {
      if (requestError instanceof ApiError && requestError.code === "BANK_AUTH_DECLINED") {
        setBankError(requestError.message);
      } else {
        setBankError(requestError instanceof Error ? requestError.message : "Bank verification failed.");
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className={`shopper-shell ${embedded ? "shopper-shell--embedded" : ""}`} style={merchantThemeStyle(merchantTheme.accent_color)}>
      <header className="shopper-header">
        <a className="brand" href={`/storefront?merchant=${encodeURIComponent(merchantId)}`}>
          {merchantTheme.logo_url ? (
            <img className="brand-logo" src={merchantTheme.logo_url} alt={merchantTheme.name} />
          ) : (
            <span>{merchantTheme.name}</span>
          )}
          <small>Powered by Sway</small>
        </a>
        <div className="shopper-header-actions">
          <div className="limit-control">
            <button
              type="button"
              className="limit-button"
              onClick={() => setLimitOpen((value) => !value)}
            >
              <CircleDollarSign size={15} />
              <span>{budgetCents === null ? "Set spending limit" : `${money(budgetCents)} limit active`}</span>
            </button>
            {limitOpen ? (
              <form className="limit-form" onSubmit={saveLimit}>
                <label htmlFor="spending-limit">Maximum for this shopping session</label>
                <div>
                  <span>S$</span>
                  <input
                    id="spending-limit"
                    type="number"
                    min="1"
                    max="500"
                    step="1"
                    value={limitDraft}
                    onChange={(event) => setLimitDraft(event.target.value)}
                    placeholder="100"
                    autoFocus
                  />
                </div>
                <div className="limit-form-actions">
                  <button type="submit" className="small-primary" disabled={busy}>
                    Apply
                  </button>
                  {budgetCents !== null ? (
                    <button type="button" className="text-link" onClick={() => void clearLimit()}>
                      Clear
                    </button>
                  ) : null}
                  <button
                    type="button"
                    className="icon-button"
                    onClick={() => setLimitOpen(false)}
                    aria-label="Close spending limit"
                  >
                    <X size={18} />
                  </button>
                </div>
              </form>
            ) : null}
          </div>
          <AccountMenu account={account} onChange={onAccountChange} />
        </div>
      </header>

      <main className="shopper-layout">
        <section className="commerce-canvas">
          <div className="chat-scroll">
            <div className="chat-column">
              {messages.length <= 1 ? (
                <div className="conversation-intro">
                  <h1>What does your skin need today?</h1>
                </div>
              ) : null}

              <div className="conversation" aria-live="polite">
                {messages.map((message) => (
                  <div key={message.id} className="message-group">
                    <div className={`message message--${message.role}`}>
                      {message.role === "assistant" ? <span className="assistant-mark" aria-hidden="true">S</span> : null}
                      <div>
                        {message.role === "assistant" ? (
                          <MessageText text={message.text} titles={knownTitles} />
                        ) : (
                          message.text
                        )}
                      </div>
                    </div>
                    {message.products?.length ? (
                      <div className="message-products">
                        {message.products.map((product) => (
                          <ProductCard
                            key={product.sku}
                            product={product}
                            selected={selectedSkus.includes(product.sku)}
                            disabled={selectedSkus.length >= 3}
                            quantityInCart={basket.find((line) => line.product.sku === product.sku)?.quantity ?? 0}
                            onToggleCompare={toggleCompare}
                            onChoose={addToBasket}
                            onOpenDetails={setDetailProduct}
                          />
                        ))}
                      </div>
                    ) : null}
                  </div>
                ))}
                {busy && !cart && !bankOpen ? (
                  <div className="thinking">
                    <LoaderCircle size={15} className="spin" /> Checking what is needed…
                  </div>
                ) : null}
              </div>

              {error ? <div className="inline-error" role="alert">{error}</div> : null}
              {decline ? (
                <section className="decline-panel" role="alert">
                  <div><X size={18} /></div>
                  <div>
                    <p>Not authorized</p>
                    <h2>{decline.reason}</h2>
                    <code>{decline.decline_code}</code>
                    <span>The shopper was not asked, the bank was not contacted, and no order was created.</span>
                  </div>
                  <button type="button" onClick={() => setLimitOpen(true)}>Change limit</button>
                </section>
              ) : null}

              {categories ? (
                <CategoryTable data={categories} busy={busy} onSelect={(key) => void browseCategory(key)} />
              ) : null}

              {routine ? (
                <RoutinePlan
                  routine={routine}
                  onChoose={addToBasket}
                  quantityFor={(sku) => basket.find((line) => line.product.sku === sku)?.quantity ?? 0}
                />
              ) : null}

              {products.length > 0 && !productsInline ? (
                <section className="results-section" aria-labelledby="results-title">
                  <header className="results-header">
                    <div>
                      <p>Catalog matches</p>
                      <h2 id="results-title">Grounded options for you</h2>
                    </div>
                    <div className="results-header-actions">
                      {selectedSkus.length > 0 ? <span>{selectedSkus.length} of 3 selected</span> : null}
                      <button
                        type="button"
                        className="view-all-button"
                        onClick={() => setProductsModalOpen(true)}
                      >
                        <LayoutGrid size={14} />
                        <span>View all ({products.length})</span>
                      </button>
                    </div>
                  </header>

                  <div className="product-rail product-rail--single-line">
                    {products.map((product) => (
                      <ProductCard
                        key={product.sku}
                        product={product}
                        selected={selectedSkus.includes(product.sku)}
                        disabled={selectedSkus.length >= 3}
                        quantityInCart={basket.find((line) => line.product.sku === product.sku)?.quantity ?? 0}
                        onToggleCompare={toggleCompare}
                        onChoose={addToBasket}
                        onOpenDetails={setDetailProduct}
                      />
                    ))}
                  </div>

                  {selectedSkus.length >= 2 ? (
                    <button type="button" className="compare-action" onClick={() => void compareProducts()} disabled={busy}>
                      <Sparkles size={16} /> Compare {selectedSkus.length} products <ArrowRight size={16} />
                    </button>
                  ) : null}
                </section>
              ) : null}

              {comparison ? <ComparisonDrawer comparison={comparison} onClose={() => setComparison(null)} onChoose={addToBasket} /> : null}
              {receipt ? <ReceiptCard receipt={receipt} /> : null}

              <div ref={messagesEndRef} />
            </div>
          </div>

          <div className="chat-footer">
            <div className="chat-column">
              <form className="composer" onSubmit={submitMessage}>
                <label htmlFor="shopper-message" className="sr-only">Ask about skincare products</label>
                <input
                  id="shopper-message"
                  value={input}
                  onChange={(event) => setInput(event.target.value)}
                  placeholder="Ask about products or routines"
                  disabled={!sessionId || busy}
                />
                <button type="submit" aria-label="Send message" disabled={!input.trim() || !sessionId || busy}>
                  <Send size={16} />
                </button>
              </form>
              <p className="security-footer">
                <ShieldCheck size={13} /> Exact consent · bank verification · TAP signature · simulated authorization
              </p>
            </div>
          </div>
        </section>

        <CartSidebar
          lines={basket}
          busy={busy}
          budgetCents={budgetCents}
          decline={decline}
          stage={stage}
          trustEvents={trustEvents}
          merchantName={merchantTheme.name}
          onIncrement={incrementBasketLine}
          onDecrement={decrementBasketLine}
          onRemove={removeBasketLine}
          onCheckout={() => void startCheckout()}
          onOpenLimit={() => setLimitOpen(true)}
        />
      </main>

      {productsModalOpen && products.length > 0 ? (
        <ProductsModal
          products={products}
          selectedSkus={selectedSkus}
          basketSkus={basket.map((line) => ({ sku: line.product.sku, quantity: line.quantity }))}
          busy={busy}
          onClose={() => setProductsModalOpen(false)}
          onToggleCompare={toggleCompare}
          onChoose={addToBasket}
          onOpenDetails={setDetailProduct}
          onCompare={() => void compareProducts()}
        />
      ) : null}

      {detailProduct ? (
        <ProductDetailModal
          product={detailProduct}
          selected={selectedSkus.includes(detailProduct.sku)}
          quantityInCart={basket.find((line) => line.product.sku === detailProduct.sku)?.quantity ?? 0}
          onClose={() => setDetailProduct(null)}
          onToggleCompare={toggleCompare}
          onChoose={addToBasket}
        />
      ) : null}

      {cart && anonymous ? (
        <p className="guest-checkout-hint">
          You are checking out as a guest. Sign in to use your saved shipping address.
        </p>
      ) : null}
      {cart ? (
        <ConsentSheet
          cart={cart}
          busy={busy}
          receiptEmail={receiptEmail}
          emailError={emailError}
          onReceiptEmailChange={(value) => { setReceiptEmail(value); setEmailError(null); }}
          onChangeCard={() => { setCardError(null); setCardPromptOpen(true); }}
          onCancel={() => { setCart(null); setStage(products.length ? "products" : "start"); }}
          onConfirm={() => void confirmCart()}
        />
      ) : null}
      {bankOpen && consent ? (
        <BankSheet
          amountCents={consent.amount_cents}
          merchantName={merchantTheme.name}
          busy={busy}
          error={bankError}
          onBack={() => setBankOpen(false)}
          onVerify={(code) => void verifyBank(code)}
        />
      ) : null}
      {cardPromptOpen ? (
        <CardPrompt
          busy={cardBusy}
          error={cardError}
          onSubmit={(details) => void submitCard(details)}
          onClose={() => setCardPromptOpen(false)}
        />
      ) : null}
      {addressPromptOpen ? (
        <AddressPrompt
          account={account}
          busy={addressBusy}
          error={addressError}
          onSubmit={(address) => void submitAddress(address)}
          onClose={() => setAddressPromptOpen(false)}
        />
      ) : null}
    </div>
  );
}
