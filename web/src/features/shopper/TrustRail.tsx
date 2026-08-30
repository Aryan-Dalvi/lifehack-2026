import { Check, Circle, LockKeyhole, ShieldCheck, X } from "lucide-react";
import type { TrustEvent } from "../../types";

export type JourneyStage =
  | "start"
  | "products"
  | "comparison"
  | "preview"
  | "consented"
  | "bank"
  | "paid"
  | "declined";

type Props = {
  stage: JourneyStage;
  budgetCents: number | null;
  events: TrustEvent[];
  /** The shop this session is with. Every merchant used to be told "Mysa Skin". */
  merchantName?: string;
  isCollapsibleContent?: boolean;
};

const stepIndex: Record<JourneyStage, number> = {
  start: 0,
  products: 1,
  comparison: 1,
  preview: 3,
  consented: 4,
  bank: 5,
  paid: 7,
  declined: 2,
};

export function TrustRail({
  stage,
  budgetCents,
  events,
  merchantName,
  isCollapsibleContent = false,
}: Props) {
  const index = stepIndex[stage];
  const shop = merchantName?.trim() || "this shop";
  const steps = [
    ["Catalog verified", `Product facts come from ${shop}.`],
    ["Your limit", budgetCents === null ? "Optional · not set" : `S$${(budgetCents / 100).toFixed(2)} active`],
    ["Cart preview", stage === "declined" ? "Stopped before bank contact" : "Items and pricing rechecked"],
    ["Your confirmation", "Bound to this exact transaction"],
    ["Bank verification", "Cart-bound, single-use approval"],
    ["Agent verified", "TAP payer signature and nonce"],
    ["Payment", "One idempotent authorization"],
  ];
  const latestFailure = [...events].reverse().find((event) => event.status === "fail");

  return (
    <div className={`trust-rail ${isCollapsibleContent ? "trust-rail--collapsible" : ""}`} aria-label="Purchase protection">
      {!isCollapsibleContent ? (
        <div className="trust-title">
          <ShieldCheck size={21} />
          <h2>Purchase protection</h2>
        </div>
      ) : null}
      <ol>
        {steps.map(([label, detail], position) => {
          const failed = stage === "declined" && position === 2;
          const complete = position < index && !failed;
          const active = position === index && stage !== "paid" && !failed;
          return (
            <li key={label} className={`${complete ? "is-complete" : ""} ${active ? "is-active" : ""} ${failed ? "is-failed" : ""}`}>
              <span className="trust-marker" aria-hidden="true">
                {failed ? <X size={14} /> : complete || stage === "paid" ? <Check size={14} /> : active ? position + 1 : <Circle size={8} />}
              </span>
              <div>
                <strong>{label}</strong>
                <p>{failed && latestFailure ? latestFailure.label : detail}</p>
              </div>
            </li>
          );
        })}
      </ol>
      <div className="simulation-note">
        <LockKeyhole size={15} />
        <span><strong>Simulation mode</strong> · no real card is charged</span>
      </div>
      <details className="evidence-details">
        <summary>{events.length} verification events</summary>
        <ul>
          {events.slice(-5).map((event) => (
            <li key={event.seq}>
              <span className={`evidence-dot evidence-dot--${event.status}`} />
              {event.label}
            </li>
          ))}
        </ul>
      </details>
    </div>
  );
}

