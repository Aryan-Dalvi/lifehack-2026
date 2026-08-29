import { ArrowRight, CircleDollarSign, LayoutGrid, LoaderCircle, Send, ShieldCheck, ShoppingBag, Sparkles, X } from "lucide-react";
import { type FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { ApiError, api, money, setSessionToken } from "../../api";
import { DEFAULT_MERCHANT_ACCENT, merchantThemeStyle } from "../../theme";
import type { CartPreview, Comparison, Consent, Product, Receipt, Routine, TrustEvent, TurnEvent } from "../../types";
import { type Account, AccountMenu } from "./AccountMenu";
import { AddressPrompt } from "./AddressPrompt";
import type { BasketLine } from "./CartDrawer";
import { CartSidebar } from "./CartSidebar";
import { BankSheet, ConsentSheet, ReceiptCard } from "./CheckoutSheets";
import { ComparisonDrawer } from "./ComparisonDrawer";
import { ProductCard } from "./ProductCard";
import { ProductsModal } from "./ProductsModal";
import { RoutinePlan } from "./RoutinePlan";
import type { JourneyStage } from "./TrustRail";

type ChatMessage = { id: string; role: "assistant" | "shopper"; text: string };
type Decline = {
  decline_code: string;
  reason: string;
  total_cents?: number;
  cap_cents?: number;
};
type MerchantTheme = { name: string; accent_color: string };

const initialMessage: ChatMessage = {
  id: "welcome",
  role: "assistant",
  text: "I can help you find gentle, catalog-verified skincare. What is your main concern right now, and is your skin easily sensitive?",
};

function newMessage(role: ChatMessage["role"], text: string): ChatMessage {
  return { id: crypto.randomUUID(), role, text };
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
  const [merchantTheme, setMerchantTheme] = useState<MerchantTheme>({
    name: "Mysa Skin",
    accent_color: DEFAULT_MERCHANT_ACCENT,
  });
  const idempotencyKey = useRef(crypto.randomUUID());
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, products, routine, decline, comparison, receipt, busy]);

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
        setProducts(nextProducts);
        setSelectedSkus([]);
        setComparison(null);
        setStage("products");
      }
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

  const findProduct = (sku: string): Product | undefined =>
    products.find((product) => product.sku === sku) ?? comparison?.products.find((product) => product.sku === sku);

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
        setCart(response.data as CartPreview);
        setStage("preview");
      }
      await loadTrust(sessionId);
    } catch (requestError) {
      if (requestError instanceof ApiError && requestError.code === "ADDRESS_REQUIRED") {
        setAddressPromptOpen(true);
      } else {
        setError(requestError instanceof Error ? requestError.message : "The transaction preview could not be created.");
      }
    } finally {
      setBusy(false);
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
    setBusy(true);
    setError(null);
    try {
      const confirmed = await api<Consent>("/agent/confirm", {
        method: "POST",
        body: JSON.stringify({ session_id: sessionId, cart_id: cart.cart_id, confirmation: { method: "click" } }),
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
        <a className="brand" href="/storefront?merchant=m_mysa">
          <span>{merchantTheme.name}</span>
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
                  <div key={message.id} className={`message message--${message.role}`}>
                    {message.role === "assistant" ? <span className="assistant-mark" aria-hidden="true">S</span> : null}
                    <div>{message.text}</div>
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

              {routine ? (
                <RoutinePlan
                  routine={routine}
                  onChoose={addToBasket}
                  quantityFor={(sku) => basket.find((line) => line.product.sku === sku)?.quantity ?? 0}
                />
              ) : null}

              {products.length > 0 ? (
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
          onCompare={() => void compareProducts()}
        />
      ) : null}

      {cart && anonymous ? (
        <p className="guest-checkout-hint">
          You are checking out as a guest. Sign in to use your saved shipping address.
        </p>
      ) : null}
      {cart ? <ConsentSheet cart={cart} busy={busy} onCancel={() => { setCart(null); setStage(products.length ? "products" : "start"); }} onConfirm={() => void confirmCart()} /> : null}
      {bankOpen && consent ? <BankSheet amountCents={consent.amount_cents} busy={busy} error={bankError} onBack={() => setBankOpen(false)} onVerify={(code) => void verifyBank(code)} /> : null}
      {addressPromptOpen ? (
        <AddressPrompt
          account={account}
          busy={addressBusy}
          error={addressError}
          onSubmit={(address) => void submitAddress(address)}
          onClose={() => setAddressPromptOpen(false)}
        />
      ) : null}
      <div className="security-footer"><ShieldCheck size={14} /> Exact consent · bank verification · TAP signature · simulated authorization</div>
    </div>
  );
}
