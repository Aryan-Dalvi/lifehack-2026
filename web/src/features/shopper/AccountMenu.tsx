import { LogOut, User } from "lucide-react";
import { type FormEvent, useState } from "react";
import { ApiError, api, setConsumerToken } from "../../api";

export type Account = { consumer_id: string; email: string; display_name: string };

type AuthResponse = Account & { token: string };

/**
 * Sign-in for the storefront. Signing in is optional by design: browsing, search, routines
 * and comparison all work anonymously. An account is what makes a shopper's saved shipping
 * address and past orders reachable, so checkout is where it starts to matter.
 */
export function AccountMenu({
  account,
  onChange,
}: {
  account: Account | null;
  onChange: (account: Account | null) => void;
}) {
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const payload = await api<AuthResponse>(`/consumer/${mode}`, {
        method: "POST",
        body: JSON.stringify(
          mode === "register" ? { email, password, display_name: email.split("@")[0] } : { email, password },
        ),
      });
      setConsumerToken(payload.token);
      onChange({
        consumer_id: payload.consumer_id,
        email: payload.email,
        display_name: payload.display_name,
      });
      setOpen(false);
      setPassword("");
    } catch (requestError) {
      setError(
        requestError instanceof ApiError ? requestError.message : "Sign in could not be completed.",
      );
    } finally {
      setBusy(false);
    }
  };

  const signOut = async () => {
    try {
      await api("/consumer/logout", { method: "POST" });
    } catch {
      /* the local token is cleared regardless */
    }
    setConsumerToken(null);
    onChange(null);
  };

  if (account) {
    return (
      <div className="account-menu">
        <span className="account-who">
          <User size={14} /> {account.display_name || account.email}
        </span>
        <button type="button" className="account-link" onClick={signOut}>
          <LogOut size={14} /> Sign out
        </button>
      </div>
    );
  }

  return (
    <div className="account-menu">
      <span className="account-who account-anon">Browsing as guest</span>
      <button type="button" className="account-link" onClick={() => setOpen((value) => !value)}>
        <User size={14} /> Sign in
      </button>
      {open ? (
        <form className="account-form" onSubmit={submit}>
          <div className="account-tabs">
            <button
              type="button"
              className={mode === "login" ? "is-active" : ""}
              onClick={() => setMode("login")}
            >
              Sign in
            </button>
            <button
              type="button"
              className={mode === "register" ? "is-active" : ""}
              onClick={() => setMode("register")}
            >
              Create account
            </button>
          </div>
          <label>
            Email
            <input
              type="email"
              value={email}
              autoComplete="email"
              required
              onChange={(event) => setEmail(event.target.value)}
            />
          </label>
          <label>
            Password
            <input
              type="password"
              value={password}
              autoComplete={mode === "register" ? "new-password" : "current-password"}
              minLength={mode === "register" ? 8 : 1}
              required
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>
          {error ? <p className="account-error">{error}</p> : null}
          <button type="submit" className="account-submit" disabled={busy}>
            {busy ? "Working…" : mode === "register" ? "Create account" : "Sign in"}
          </button>
          <p className="account-hint">You can keep browsing without an account.</p>
        </form>
      ) : null}
    </div>
  );
}
