import { CreditCard, LockKeyhole, X } from "lucide-react";
import { type FormEvent, useState } from "react";

type Props = {
  busy: boolean;
  error: string | null;
  onSubmit: (card: {
    number: string;
    expiry_month: number;
    expiry_year: number;
    cvc: string;
    holder: string;
  }) => void;
  onClose: () => void;
};

function groupNumber(value: string): string {
  const digits = value.replace(/\D/g, "").slice(0, 19);
  return digits.replace(/(.{4})/g, "$1 ").trim();
}

function groupExpiry(value: string): string {
  const digits = value.replace(/\D/g, "").slice(0, 4);
  return digits.length > 2 ? `${digits.slice(0, 2)}/${digits.slice(2)}` : digits;
}

/** The one screen where the shopper hands over a card. Nothing is charged from here — this
 *  only tells the session which card the cart preview and the bank step will refer to. */
export function CardPrompt({ busy, error, onSubmit, onClose }: Props) {
  const [holder, setHolder] = useState("");
  const [number, setNumber] = useState("");
  const [expiry, setExpiry] = useState("");
  const [cvc, setCvc] = useState("");

  const [month, year] = expiry.split("/");
  const complete =
    holder.trim().length >= 2 &&
    number.replace(/\D/g, "").length >= 13 &&
    (month ?? "").length === 2 &&
    (year ?? "").length === 2 &&
    cvc.length >= 3;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!complete) return;
    onSubmit({
      number: number.replace(/\s/g, ""),
      expiry_month: Number(month),
      expiry_year: 2000 + Number(year),
      cvc,
      holder: holder.trim(),
    });
  };

  return (
    <div className="sheet-backdrop" role="presentation">
      <section className="card-sheet" role="dialog" aria-modal="true" aria-labelledby="card-title">
        <header>
          <div>
            <p>Payment method</p>
            <h2 id="card-title">Add the card you want to pay with</h2>
          </div>
          <button className="icon-button" type="button" onClick={onClose} aria-label="Close payment method">
            <X size={20} />
          </button>
        </header>

        <form onSubmit={submit}>
          <label>
            Name on card
            <input
              value={holder}
              onChange={(event) => setHolder(event.target.value)}
              autoComplete="cc-name"
              placeholder="As printed on the card"
              autoFocus
            />
          </label>
          <label>
            Card number
            <span className="card-number-field">
              <CreditCard size={16} />
              <input
                value={number}
                onChange={(event) => setNumber(groupNumber(event.target.value))}
                inputMode="numeric"
                autoComplete="cc-number"
                placeholder="4111 1111 1111 1111"
              />
            </span>
          </label>
          <div className="card-field-pair">
            <label>
              Expiry
              <input
                value={expiry}
                onChange={(event) => setExpiry(groupExpiry(event.target.value))}
                inputMode="numeric"
                autoComplete="cc-exp"
                placeholder="MM/YY"
              />
            </label>
            <label>
              Security code
              <input
                value={cvc}
                onChange={(event) => setCvc(event.target.value.replace(/\D/g, "").slice(0, 4))}
                inputMode="numeric"
                autoComplete="cc-csc"
                placeholder="123"
              />
            </label>
          </div>

          {error ? <p className="form-error" role="alert">{error}</p> : null}

          <p className="card-privacy">
            <LockKeyhole size={14} /> Only the brand, expiry and last four digits are kept. The card
            number is checked and discarded — it is never stored, and the shopping model never sees it.
          </p>
          <button type="submit" className="primary-button" disabled={!complete || busy}>
            {busy ? "Checking the card…" : "Use this card"}
          </button>
        </form>
      </section>
    </div>
  );
}
