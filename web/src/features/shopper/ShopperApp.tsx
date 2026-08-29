import { ArrowRight, CircleDollarSign, LoaderCircle, Send, Settings2, ShieldCheck, Sparkles, X } from "lucide-react";
import { type FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { ApiError, api, money } from "../../api";
import type { CartPreview, Comparison, Consent, Product, Receipt, TrustEvent, TurnEvent } from "../../types";
import { BankSheet, ConsentSheet, ReceiptCard } from "./CheckoutSheets";
import { ComparisonDrawer } from "./ComparisonDrawer";
import { ProductCard } from "./ProductCard";
import { type JourneyStage, TrustRail } from "./TrustRail";

type ChatMessage = { id: string; role: "assistant" | "shopper"; text: string };
type Decline = {
  decline_code: string;
  reason: string;
  total_cents?: number;
  cap_cents?: number;
};

const quickReplies = [
  { label: "Dryness", message: "I’m shopping for dryness and would like gentle products." },
  { label: "Sensitive skin", message: "I have sensitive skin and prefer fragrance-free products." },
  { label: "Acne-prone", message: "I’m acne-prone and want help with congestion." },
  { label: "Not sure", message: "I’m not sure what I need." },
];

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
  const [cart, setCart] = useState<CartPreview | null>(null);
  const [consent, setConsent] = useState<Consent | null>(null);
  const [receipt, setReceipt] = useState<Receipt | null>(null);
  const [decline, setDecline] = useState<Decline | null>(null);
  const [stage, setStage] = useState<JourneyStage>("start");
  const [trustEvents, setTrustEvents] = useState<TrustEvent[]>([]);
  const [input, setInput] = useState("");
  const [quickSelection, setQuickSelection] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [limitOpen, setLimitOpen] = useState(false);
  const [limitDraft, setLimitDraft] = useState("");
  const [budgetCents, setBudgetCents] = useState<number | null>(null);
  const [bankChallengeId, setBankChallengeId] = useState<string | null>(null);
  const [bankOpen, setBankOpen] = useState(false);
  const [bankError, setBankError] = useState<string | null>(null);
  const idempotencyKey = useRef(crypto.randomUUID());

  const loadTrust = useCallback(async (activeSessionId: string) => {
    const payload = await api<{ events: TrustEvent[] }>(`/trust/events/snapshot?session_id=${encodeURIComponent(activeSessionId)}`);
    setTrustEvents(payload.events);
  }, []);

  useEffect(() => {
    let active = true;
    api<{ session_id: string; greeting: string }>("/agent/session", {
      method: "POST",
      body: JSON.stringify({ merchant_id: merchantId, category: "skincare", consumer_id: "usr_demo", budget_cents: null }),
    })
      .then((payload) => {
        if (!active) return;
        setSessionId(payload.session_id);
        return loadTrust(payload.session_id);
      })
      .catch((requestError: Error) => active && setError(requestError.message));
    return () => {
      active = false;
    };
  }, [loadTrust, merchantId]);

  const applyEvents = (events: TurnEvent[], suppressToken = false) => {
    for (const event of events) {
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

  const chooseProduct = async (sku: string) => {
    if (!sessionId || busy) return;
    setBusy(true);
    setError(null);
    setDecline(null);
    try {
      const response = await api<{ type: "cart"; data: CartPreview | (Decline & { status: "declined" }) }>("/agent/action", {
        method: "POST",
        body: JSON.stringify({ session_id: sessionId, action: "select", sku, quantity: 1 }),
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
      setError(requestError instanceof Error ? requestError.message : "The transaction preview could not be created.");
    } finally {
      setBusy(false);
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
          consumer_id: "usr_demo",
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
    <div className={`shopper-shell ${embedded ? "shopper-shell--embedded" : ""}`}>
      <header className="shopper-header">
        <a className="brand" href="/storefront?merchant=m_mysa"><span>Mysa Skin</span><small>Powered by Sway</small></a>
        {!embedded ? <a className="merchant-link" href="/admin"><Settings2 size={16} /> Merchant setup</a> : null}
      </header>
      <main className="shopper-layout">
        <section className="commerce-canvas">
          <div className="conversation-intro">
            <h1>What does your skin need today?</h1>
            <p>Skincare guidance grounded in the merchant’s current catalog.</p>
          </div>

          <div className="conversation" aria-live="polite">
            {messages.map((message) => (
              <div key={message.id} className={`message message--${message.role}`}>
                {message.role === "assistant" ? <span className="assistant-mark" aria-hidden="true">S</span> : null}
                <div>{message.text}</div>
              </div>
            ))}
            {busy && !cart && !bankOpen ? <div className="thinking"><LoaderCircle size={16} className="spin" /> Checking what is needed…</div> : null}
          </div>

          <div className="quick-replies" aria-label="Quick replies">
            {quickReplies.map((reply) => (
                <button
                  type="button"
                  key={reply.label}
                  className={quickSelection === reply.label ? "active" : ""}
                  aria-pressed={quickSelection === reply.label}
                  onClick={() => {
                    setQuickSelection(reply.label);
                    void sendText(reply.message, { showShopperMessage: false, suppressToken: true });
                  }}
                  disabled={!sessionId || busy}
                >
                  {reply.label}<ArrowRight size={14} />
                </button>
            ))}
          </div>

          <form className="composer" onSubmit={submitMessage}>
            <label htmlFor="shopper-message" className="sr-only">Ask about skincare products</label>
            <input
              id="shopper-message"
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder="Ask about products or routines"
              disabled={!sessionId || busy}
            />
            <button type="submit" aria-label="Send message" disabled={!input.trim() || !sessionId || busy}><Send size={18} /></button>
          </form>

          <div className="control-row">
            <button type="button" className="limit-button" onClick={() => setLimitOpen((value) => !value)}>
              <CircleDollarSign size={17} />
              {budgetCents === null ? "Set a spending limit" : `${money(budgetCents)} limit active`}
            </button>
            <span>Optional · add, change or clear it any time</span>
          </div>
          {limitOpen ? (
            <form className="limit-form" onSubmit={saveLimit}>
              <label htmlFor="spending-limit">Maximum for this shopping session</label>
              <div><span>S$</span><input id="spending-limit" type="number" min="1" max="500" step="1" value={limitDraft} onChange={(event) => setLimitDraft(event.target.value)} placeholder="100" autoFocus /></div>
              <button type="submit" className="small-primary" disabled={busy}>Apply limit</button>
              {budgetCents !== null ? <button type="button" className="text-link" onClick={() => void clearLimit()}>Clear limit</button> : null}
              <button type="button" className="icon-button" onClick={() => setLimitOpen(false)} aria-label="Close spending limit"><X size={18} /></button>
            </form>
          ) : null}

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

          {products.length > 0 ? (
            <section className="results-section" aria-labelledby="results-title">
              <header>
                <div><p>Catalog matches</p><h2 id="results-title">Grounded options for you</h2></div>
                {selectedSkus.length > 0 ? <span>{selectedSkus.length} of 3 selected</span> : null}
              </header>
              <div className="product-rail">
                {products.map((product) => (
                  <ProductCard key={product.sku} product={product} selected={selectedSkus.includes(product.sku)} disabled={selectedSkus.length >= 3} onToggleCompare={toggleCompare} onChoose={(sku) => void chooseProduct(sku)} />
                ))}
              </div>
              {selectedSkus.length >= 2 ? (
                <button type="button" className="compare-action" onClick={() => void compareProducts()} disabled={busy}>
                  <Sparkles size={17} /> Compare {selectedSkus.length} products <ArrowRight size={17} />
                </button>
              ) : null}
            </section>
          ) : null}

          {comparison ? <ComparisonDrawer comparison={comparison} onClose={() => setComparison(null)} onChoose={(sku) => void chooseProduct(sku)} /> : null}
          {receipt ? <ReceiptCard receipt={receipt} /> : null}
        </section>
        <TrustRail stage={stage} budgetCents={budgetCents} events={trustEvents} />
      </main>

      {cart ? <ConsentSheet cart={cart} busy={busy} onCancel={() => { setCart(null); setStage(products.length ? "products" : "start"); }} onConfirm={() => void confirmCart()} /> : null}
      {bankOpen && consent ? <BankSheet amountCents={consent.amount_cents} busy={busy} error={bankError} onBack={() => setBankOpen(false)} onVerify={(code) => void verifyBank(code)} /> : null}
      <div className="security-footer"><ShieldCheck size={14} /> Exact consent · bank verification · TAP signature · simulated authorization</div>
    </div>
  );
}
