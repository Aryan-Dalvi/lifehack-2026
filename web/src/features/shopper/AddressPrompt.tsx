import { MapPin, X } from "lucide-react";
import { type FormEvent, useState } from "react";
import type { Account } from "./AccountMenu";

type Props = {
  account: Account | null;
  busy: boolean;
  error: string | null;
  onSubmit: (address: { recipient: string; lines: string[]; postal_code: string; country: string }) => void;
  onClose: () => void;
};

/**
 * Shown when checkout returns ADDRESS_REQUIRED. Adding an address needs a signed-in
 * account (the backend attaches it to a consumer, not an anonymous session), so this
 * points the shopper at the account menu rather than trying to collect an address for
 * no one in particular.
 */
export function AddressPrompt({ account, busy, error, onSubmit, onClose }: Props) {
  const [recipient, setRecipient] = useState("");
  const [line1, setLine1] = useState("");
  const [line2, setLine2] = useState("");
  const [postalCode, setPostalCode] = useState("");

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const lines = [line1, line2].map((line) => line.trim()).filter(Boolean);
    if (!recipient.trim() || lines.length === 0 || !postalCode.trim()) return;
    onSubmit({ recipient: recipient.trim(), lines, postal_code: postalCode.trim(), country: "SG" });
  };

  return (
    <div className="sheet-backdrop" role="presentation">
      <section className="checkout-sheet address-prompt" role="dialog" aria-modal="true" aria-labelledby="address-title">
        <header>
          <div>
            <p>One thing before checkout</p>
            <h2 id="address-title">Add a shipping address</h2>
          </div>
          <button className="icon-button" type="button" onClick={onClose} aria-label="Close"><X size={20} /></button>
        </header>

        {!account ? (
          <div className="address-signin-hint">
            <MapPin size={20} />
            <p>Sign in first, using the account menu at the top of the page — a shipping address is saved to your account, not to this browsing session. Then try checkout again.</p>
          </div>
        ) : (
          <form onSubmit={submit} className="address-form">
            <label htmlFor="addr-recipient">Recipient name</label>
            <input id="addr-recipient" value={recipient} onChange={(event) => setRecipient(event.target.value)} placeholder="N. Shopper" required autoFocus />

            <label htmlFor="addr-line1">Address</label>
            <input id="addr-line1" value={line1} onChange={(event) => setLine1(event.target.value)} placeholder="14 Prince George's Park" required />
            <input aria-label="Address line 2 (optional)" value={line2} onChange={(event) => setLine2(event.target.value)} placeholder="#05-21 (optional)" />

            <label htmlFor="addr-postal">Postal code</label>
            <input id="addr-postal" value={postalCode} onChange={(event) => setPostalCode(event.target.value)} placeholder="118420" required />

            {error ? <p className="form-error" role="alert">{error}</p> : null}
            <button type="submit" className="primary-button" disabled={busy}>
              {busy ? "Saving…" : "Save address and continue"}
            </button>
          </form>
        )}
      </section>
    </div>
  );
}
