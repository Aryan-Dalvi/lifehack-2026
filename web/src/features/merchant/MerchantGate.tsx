import {
  ArrowRight,
  ChevronDown,
  KeyRound,
  LoaderCircle,
  LockKeyhole,
  Play,
  Plus,
  Store,
  X,
} from "lucide-react";
import { type FormEvent, useEffect, useState } from "react";
import { type RememberedStore, api, forgetStore, rememberedStores } from "../../api";

type DemoStore = {
  available: boolean;
  merchant_id: string | null;
  name: string | null;
  api_key: string | null;
};

type Props = {
  busy: boolean;
  creating: boolean;
  error: string | null;
  /** Open a store with a key that is already known — a remembered store, or the demo. */
  onOpen: (store: { merchant_id?: string; name?: string; key: string }) => void;
  onCreate: (name: string, size: "sme" | "enterprise") => void;
};

/**
 * The front door to the merchant admin.
 *
 * It used to be two bare forms asking for an API key, which is the least likely thing a
 * visitor has. The paths are now ordered by how likely they are to be the right one: a store
 * this browser already opened, the demo, a new store, and — last, folded away — the key.
 */
export function MerchantGate({ busy, creating, error, onOpen, onCreate }: Props) {
  const [stores, setStores] = useState<RememberedStore[]>(() => rememberedStores());
  const [demo, setDemo] = useState<DemoStore | null>(null);
  const [keyOpen, setKeyOpen] = useState(false);
  const [whyOpen, setWhyOpen] = useState(false);

  useEffect(() => {
    let active = true;
    // `available: false` is a normal answer — an unseeded or locked-down deployment has no
    // demo store to offer, and the button simply is not drawn.
    api<DemoStore>("/merchant/demo-store")
      .then((payload) => active && setDemo(payload))
      .catch(() => active && setDemo(null));
    return () => {
      active = false;
    };
  }, []);

  const forget = (merchantId: string) => {
    forgetStore(merchantId);
    setStores(rememberedStores());
  };

  const submitCreate = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const name = String(form.get("name") ?? "").trim();
    if (!name) return;
    onCreate(name, String(form.get("size") ?? "sme") === "enterprise" ? "enterprise" : "sme");
  };

  const submitKey = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const value = new FormData(event.currentTarget).get("key");
    const key = typeof value === "string" ? value.trim() : "";
    if (key) onOpen({ key });
  };

  return (
    <main className="gate">
      <section className="gate-brand">
        <a className="gate-logo" href="/">Sway</a>
        <h1>Your catalog, ready to talk back.</h1>
        <p>
          Bring a spreadsheet. Leave with a shopping agent that only ever quotes your real
          products, your real prices and your real stock — and a checkout the shopper confirms
          line by line.
        </p>
        <ul className="gate-points">
          <li><Store size={15} /> Your own catalog, agent and storefront</li>
          <li><LockKeyhole size={15} /> Nobody else's store can read yours</li>
          <li><Play size={15} /> Live in about 90 seconds</li>
        </ul>
      </section>

      <section className="gate-panel" aria-labelledby="gate-title">
        <h2 id="gate-title">Open your store</h2>

        {stores.length > 0 ? (
          <div className="gate-block">
            <p className="gate-block-label">On this device</p>
            <ul className="gate-stores">
              {stores.map((store) => (
                <li key={store.merchant_id}>
                  <button
                    type="button"
                    className="gate-store"
                    disabled={busy}
                    onClick={() => onOpen({ merchant_id: store.merchant_id, name: store.name, key: store.key })}
                  >
                    <span className="gate-store-mark" aria-hidden="true">
                      {(store.name || "?").trim().charAt(0).toUpperCase()}
                    </span>
                    <span className="gate-store-text">
                      <strong>{store.name || store.merchant_id}</strong>
                      <small>{store.merchant_id}</small>
                    </span>
                    <ArrowRight size={16} />
                  </button>
                  <button
                    type="button"
                    className="gate-forget"
                    onClick={() => forget(store.merchant_id)}
                    aria-label={`Forget ${store.name || store.merchant_id} on this device`}
                  >
                    <X size={14} />
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {/* Once the demo is in the remembered list it is already one click away; offering it
            twice would just be two buttons that do the same thing. */}
        {demo?.available && demo.api_key && !stores.some((store) => store.merchant_id === demo.merchant_id) ? (
          <button
            type="button"
            className="gate-demo"
            disabled={busy}
            onClick={() =>
              onOpen({
                merchant_id: demo.merchant_id ?? undefined,
                name: demo.name ?? undefined,
                key: demo.api_key as string,
              })
            }
          >
            <Play size={16} />
            <span>
              <strong>Open the demo store</strong>
              <small>{demo.name} · a stocked catalog, nothing to type</small>
            </span>
            <ArrowRight size={16} />
          </button>
        ) : null}

        <div className="gate-block">
          <p className="gate-block-label">
            {stores.length > 0 || demo?.available ? "Or start a new one" : "Create your store"}
          </p>
          <form className="gate-create" onSubmit={submitCreate}>
            <label className="sr-only" htmlFor="gate-store-name">Your store name</label>
            <input
              id="gate-store-name"
              name="name"
              type="text"
              placeholder="Your store name"
              maxLength={100}
              autoComplete="organization"
              required
            />
            <label className="sr-only" htmlFor="gate-store-size">Business size</label>
            <div className="gate-select">
              <select id="gate-store-size" name="size" defaultValue="sme">
                <option value="sme">Small business</option>
                <option value="enterprise">Large retailer</option>
              </select>
              <ChevronDown size={15} aria-hidden="true" />
            </div>
            <button type="submit" className="gate-primary" disabled={creating || busy}>
              {creating ? (
                <><LoaderCircle className="spin" size={15} /> Creating your store…</>
              ) : (
                <><Plus size={15} /> Create my store</>
              )}
            </button>
          </form>
        </div>

        <div className="gate-fold">
          <button type="button" className="gate-fold-toggle" aria-expanded={keyOpen} onClick={() => setKeyOpen((open) => !open)}>
            <KeyRound size={14} /> I have a store key
            <ChevronDown size={14} className={keyOpen ? "gate-chevron gate-chevron--open" : "gate-chevron"} />
          </button>
          {keyOpen ? (
            <form className="gate-key" onSubmit={submitKey}>
              <label className="sr-only" htmlFor="gate-key">Merchant API key</label>
              <input id="gate-key" name="key" type="password" placeholder="mk_…" autoComplete="off" required autoFocus />
              <button type="submit" disabled={busy}>Open</button>
            </form>
          ) : null}
        </div>

        {error ? <p className="gate-error" role="alert">{error}</p> : null}

        <div className="gate-fold gate-fold--quiet">
          <button type="button" className="gate-fold-toggle" aria-expanded={whyOpen} onClick={() => setWhyOpen((open) => !open)}>
            <LockKeyhole size={14} /> Why a key, and where it is kept
            <ChevronDown size={14} className={whyOpen ? "gate-chevron gate-chevron--open" : "gate-chevron"} />
          </button>
          {whyOpen ? (
            <div className="gate-why">
              <p>
                One deployment serves every merchant, so every request has to say which store it
                is for. Your key is that answer: it is sent as <code>X-Merchant-Key</code> and
                the server scopes each query to the store it resolves to. Another merchant's key
                cannot read your catalog, your margins or your shoppers' carts — not because the
                page hides them, but because the query never reaches them.
              </p>
              <p>
                Keys are stored only as a hash, which is why yours is shown once. This browser
                keeps the stores you open in its own local storage so you do not have to paste it
                again; <strong>Forget</strong> removes one, and anyone with access to this device
                and browser profile can open the stores listed above.
              </p>
            </div>
          ) : null}
        </div>
      </section>
    </main>
  );
}
