import { Moon, ShieldCheck, Sun } from "lucide-react";
import type { Routine } from "../../types";

type Props = {
  routine: Routine;
  onChoose: (sku: string) => void;
  quantityFor: (sku: string) => number;
};

export function RoutinePlan({ routine, onChoose, quantityFor }: Props) {
  const morning = routine.steps.filter((step) => step.when.includes("morning"));
  const night = routine.steps.filter((step) => step.when.includes("night"));
  const sharedCount = routine.steps.filter(
    (step) => step.when.includes("morning") && step.when.includes("night"),
  ).length;

  return (
    <section className="routine-plan" aria-labelledby="routine-title">
      <header>
        <div>
          <p>Your routine</p>
          <h2 id="routine-title">
            {morning.length} step{morning.length === 1 ? "" : "s"} in the morning ·{" "}
            {night.length} at night
          </h2>
        </div>
      </header>

      <div className="routine-glance">
        <div>
          <h3><Sun size={13} /> Morning</h3>
          <ol>
            {morning.map((step) => (
              <li key={step.sku}><span>{step.label}</span> {step.title}</li>
            ))}
          </ol>
        </div>
        <div>
          <h3><Moon size={13} /> Night</h3>
          {night.length > 0 ? (
            <ol>
              {night.map((step) => (
                <li key={step.sku}><span>{step.label}</span> {step.title}</li>
              ))}
            </ol>
          ) : (
            <p className="routine-empty">No night-only steps in this plan.</p>
          )}
        </div>
      </div>

      {routine.usage_detail && sharedCount > 0 ? (
        <p className="routine-note">
          {sharedCount} of these {sharedCount === 1 ? "is" : "are"} used at both times of day —
          gentle cleansing and moisturising do not need to differ. Steps that are genuinely
          time-specific, like sun protection, are marked morning-only.
        </p>
      ) : null}

      <ol className="routine-steps">
        {routine.steps.map((step) => {
          const inCart = quantityFor(step.sku);
          return (
            <li key={step.sku}>
              <span className="routine-order" aria-hidden="true">{step.order}</span>
              <div className="routine-body">
                <div className="routine-head">
                  <strong>{step.label}</strong>
                  <span className="routine-when">
                    {step.when.includes("morning") ? (
                      <span className="when-chip"><Sun size={12} /> Morning</span>
                    ) : null}
                    {step.when.includes("night") ? (
                      <span className="when-chip"><Moon size={12} /> Night</span>
                    ) : null}
                  </span>
                </div>
                <p className="routine-product">{step.title}</p>
                {step.advice ? <p className="routine-advice">{step.advice}</p> : null}
                {step.alternatives > 0 ? (
                  <span className="routine-alts">{step.alternatives} other option{step.alternatives > 1 ? "s" : ""} in this step</span>
                ) : null}
              </div>
              <button
                type="button"
                className={`routine-add ${inCart > 0 ? "routine-add--in-cart" : ""}`}
                onClick={() => onChoose(step.sku)}
              >
                {inCart > 0 ? `In cart · ${inCart}` : "Add"}
              </button>
            </li>
          );
        })}
      </ol>

      {!routine.usage_detail ? (
        <p className="routine-hint">Ask “how do I use these?” for step-by-step guidance.</p>
      ) : null}

      {routine.missing_steps.length > 0 ? (
        <p className="routine-gap">
          No match in stock for: {routine.missing_steps.map((step) => step.label).join(", ")}. Filters
          you set were kept rather than relaxed.
        </p>
      ) : null}

      <p className="routine-source">
        <ShieldCheck size={13} /> Steps and order built from catalog data
        {routine.phrasing_source === "openai_responses" ? " · wording by the model, every product verified" : " · wording generated without a model call"}
      </p>
    </section>
  );
}
