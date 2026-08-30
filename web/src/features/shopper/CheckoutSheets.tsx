import { ArrowLeft, Check, CreditCard, LockKeyhole, Mail, MapPin, ShieldCheck, X } from "lucide-react";
import { type FormEvent, useState } from "react";
import { money } from "../../api";
import type { CartPreview, Receipt } from "../../types";

type ConsentProps = {
  cart: CartPreview;
  busy: boolean;
  receiptEmail: string;
  emailError: string | null;
  onReceiptEmailChange: (value: string) => void;
  onChangeCard: () => void;
  onCancel: () => void;
  onConfirm: () => void;
};

export function ConsentSheet({
  cart,
  busy,
  receiptEmail,
  emailError,
  onReceiptEmailChange,
  onChangeCard,
  onCancel,
  onConfirm,
}: ConsentProps) {
  const address = cart.shipping_address;
  return (
    <div className="sheet-backdrop" role="presentation">
      <section className="checkout-sheet" role="dialog" aria-modal="true" aria-labelledby="consent-title">
        <header>
          <div>
            <p>Review before anything happens</p>
            <h2 id="consent-title">Confirm this exact purchase</h2>
          </div>
          <button className="icon-button" type="button" onClick={onCancel} aria-label="Close transaction preview"><X size={20} /></button>
        </header>

        <div className="ship-to">
          <MapPin size={20} />
          <div>
            <span>Ship to</span>
            <strong>{address.recipient}</strong>
            <p>{address.lines.join(", ")} · Singapore {address.postal_code}</p>
          </div>
          <button type="button" className="text-link">Change</button>
        </div>

        <div className="transaction-slip">
          <div><span>Merchant</span><strong>{cart.merchant}</strong></div>
          {cart.items.map((item) => (
            <div key={item.sku}><span>{item.title} × {item.quantity}</span><strong>{money(item.unit_price_cents * item.quantity)}</strong></div>
          ))}
          <div><span>Delivery</span><strong>2–4 business days</strong></div>
          <div>
            <span>Card</span>
            <strong>
              {cart.card_brand} •••• {cart.last4}
              <button type="button" className="text-link slip-change" onClick={onChangeCard}>Change</button>
            </strong>
          </div>
          <div className="total-row"><span>Total</span><strong>{money(cart.total_cents, cart.currency)}</strong></div>
        </div>

        <div className="scope-band">
          <ShieldCheck size={21} />
          <p>
            Charge this card <strong>once</strong>, for <strong>this cart</strong>, at <strong>this merchant</strong>, shipping to <strong>this address</strong>. Nothing else.
          </p>
        </div>

        <label className="receipt-email">
          <span><Mail size={16} /> Email the receipt to</span>
          <input
            type="email"
            inputMode="email"
            autoComplete="email"
            value={receiptEmail}
            aria-invalid={Boolean(emailError)}
            onChange={(event) => onReceiptEmailChange(event.target.value)}
            placeholder="you@example.com"
          />
          {emailError ? <small role="alert">{emailError}</small> : null}
        </label>

        <p className="bank-warning"><LockKeyhole size={16} /> Your bank will ask you to approve this next.</p>
        <footer>
          <button type="button" className="secondary-button" onClick={onCancel}>Cancel</button>
          <button type="button" className="primary-button" onClick={onConfirm} disabled={busy}>
            {busy ? "Securing preview…" : `Confirm & pay ${money(cart.total_cents, cart.currency)}`}
          </button>
        </footer>
      </section>
    </div>
  );
}

type BankProps = {
  amountCents: number;
  merchantName: string;
  busy: boolean;
  error: string | null;
  onBack: () => void;
  onVerify: (code: string) => void;
};

export function BankSheet({ amountCents, merchantName, busy, error, onBack, onVerify }: BankProps) {
  const [code, setCode] = useState("");
  const submit = (event: FormEvent) => {
    event.preventDefault();
    onVerify(code);
  };
  return (
    <div className="sheet-backdrop bank-backdrop" role="presentation">
      <section className="bank-sheet" role="dialog" aria-modal="true" aria-labelledby="bank-title">
        <button className="back-button" type="button" onClick={onBack}><ArrowLeft size={17} /> Return to preview</button>
        <div className="bank-brand"><span>◆</span> Meridian Bank · Visa Secure simulation</div>
        <CreditCard size={34} strokeWidth={1.4} />
        <h2 id="bank-title">Approve {money(amountCents)} at {merchantName}</h2>
        <p>A six-digit verification code was sent to •••• 8821. It is bound to this cart and can be used once.</p>
        <form onSubmit={submit}>
          <label htmlFor="bank-code">Verification code</label>
          <input
            id="bank-code"
            inputMode="numeric"
            autoComplete="one-time-code"
            maxLength={7}
            value={code}
            onChange={(event) => setCode(event.target.value.replace(/[^0-9 ]/g, ""))}
            placeholder="000 000"
            aria-invalid={Boolean(error)}
            autoFocus
          />
          <p className="demo-code">Demo code: <strong>492 118</strong></p>
          {error ? <p className="form-error" role="alert">{error}</p> : null}
          <button type="submit" className="bank-button" disabled={busy || code.replace(/\D/g, "").length !== 6}>
            {busy ? "Verifying with bank…" : "Verify and continue"}
          </button>
        </form>
        <p className="privacy-note"><LockKeyhole size={14} /> {merchantName} never sees this code. Neither does the shopping model.</p>
      </section>
    </div>
  );
}

function ReceiptDelivery({ delivery }: { delivery: NonNullable<Receipt["email_delivery"]> }) {
  const message =
    delivery.status === "sent"
      ? `Receipt emailed to ${delivery.recipient}`
      : delivery.status === "simulated"
        ? `Receipt prepared for ${delivery.recipient} — demo outbox, no mail server configured`
        : delivery.status === "skipped"
          ? "No email address was given, so no receipt was sent"
          : `The receipt to ${delivery.recipient} could not be delivered — your order is still confirmed`;
  return (
    <p className={`receipt-delivery receipt-delivery--${delivery.status}`}>
      <Mail size={14} /> {message}
    </p>
  );
}

type ReceiptProps = { receipt: Receipt };

export function ReceiptCard({ receipt }: ReceiptProps) {
  return (
    <section className="receipt-card" aria-label="Purchase receipt">
      <div className="receipt-check"><Check size={22} /></div>
      <div className="receipt-main">
        <p>Order confirmed</p>
        <h2>{money(receipt.total_cents, receipt.currency)} paid to {receipt.merchant}</h2>
        <span>
          {receipt.items[0]?.title}
          {receipt.items.length > 1 ? ` + ${receipt.items.length - 1} more` : ""} ·{" "}
          {receipt.card_brand} •••• {receipt.last4}
        </span>
      </div>
      <dl>
        <div><dt>Issuer</dt><dd>{receipt.issuer}</dd></div>
        <div><dt>Authorization</dt><dd>{receipt.auth_code}</dd></div>
        <div><dt>Order</dt><dd>{receipt.order_id}</dd></div>
      </dl>
      {receipt.email_delivery ? <ReceiptDelivery delivery={receipt.email_delivery} /> : null}
      <div className="receipt-simulation"><LockKeyhole size={14} /> Simulated authorization · no real charge</div>
    </section>
  );
}

