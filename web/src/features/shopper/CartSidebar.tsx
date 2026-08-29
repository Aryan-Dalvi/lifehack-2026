import { CircleDollarSign, Minus, Plus, ShieldCheck, ShoppingBag, Trash2, X, ChevronDown, ChevronUp } from "lucide-react";
import { useState } from "react";
import { money } from "../../api";
import type { TrustEvent } from "../../types";
import type { BasketLine } from "./CartDrawer";
import { TrustRail, type JourneyStage } from "./TrustRail";

type Decline = {
  decline_code: string;
  reason: string;
  total_cents?: number;
  cap_cents?: number;
};

type Props = {
  lines: BasketLine[];
  busy: boolean;
  budgetCents: number | null;
  decline: Decline | null;
  stage: JourneyStage;
  trustEvents: TrustEvent[];
  onIncrement: (sku: string) => void;
  onDecrement: (sku: string) => void;
  onRemove: (sku: string) => void;
  onCheckout: () => void;
  onOpenLimit: () => void;
};

export function CartSidebar({
  lines,
  busy,
  budgetCents,
  decline,
  stage,
  trustEvents,
  onIncrement,
  onDecrement,
  onRemove,
  onCheckout,
  onOpenLimit,
}: Props) {
  const [protectionOpen, setProtectionOpen] = useState(false);
  const totalCents = lines.reduce((sum, line) => sum + line.product.price_cents * line.quantity, 0);
  const totalCount = lines.reduce((sum, line) => sum + line.quantity, 0);
  const currency = lines[0]?.product.currency ?? "SGD";

  const isOverBudget = budgetCents !== null && totalCents > budgetCents;
  const overBudgetCents = isOverBudget ? totalCents - budgetCents : 0;
  const remainingCents = budgetCents !== null && totalCents <= budgetCents ? budgetCents - totalCents : null;

  return (
    <aside className="cart-sidebar" aria-label="Shopping Cart and Purchase Protection">
      {/* Header */}
      <div className="cart-sidebar-header">
        <div className="cart-sidebar-title">
          <ShoppingBag size={18} />
          <h2>Your Cart</h2>
          {totalCount > 0 ? <span className="cart-badge">{totalCount}</span> : null}
        </div>

        <button
          type="button"
          className={`cart-limit-pill ${isOverBudget ? "cart-limit-pill--over" : ""}`}
          onClick={onOpenLimit}
          title="Adjust spending limit"
        >
          <CircleDollarSign size={13} />
          <span>{budgetCents === null ? "No limit" : money(budgetCents)}</span>
        </button>
      </div>

      {/* Budget status banner if limit active */}
      {budgetCents !== null ? (
        <div className={`cart-budget-status ${isOverBudget ? "cart-budget-status--over" : ""}`}>
          <div className="cart-budget-bar-track">
            <div
              className="cart-budget-bar-fill"
              style={{
                width: `${Math.min(100, Math.round((totalCents / budgetCents) * 100))}%`,
                backgroundColor: isOverBudget ? "var(--danger)" : "var(--sage-500)",
              }}
            />
          </div>
          <div className="cart-budget-text">
            <span>{money(totalCents, currency)} of {money(budgetCents)}</span>
            {isOverBudget ? (
              <strong className="over-text">+{money(overBudgetCents, currency)} over limit</strong>
            ) : remainingCents !== null ? (
              <span className="remaining-text">{money(remainingCents, currency)} left</span>
            ) : null}
          </div>
        </div>
      ) : null}

      {/* Cart Line Items or Empty State */}
      <div className="cart-sidebar-items">
        {lines.length === 0 ? (
          <div className="cart-sidebar-empty">
            <div className="empty-icon-wrap">
              <ShoppingBag size={24} />
            </div>
            <p>Your cart is empty</p>
            <small>Ask the assistant for recommendations or select products from the chat.</small>
          </div>
        ) : (
          <ul className="cart-sidebar-lines">
            {lines.map((line) => (
              <li key={line.product.sku} className="cart-sidebar-item">
                <img
                  src={line.product.image_url ?? ""}
                  alt={line.product.title}
                  className="cart-sidebar-thumb"
                  loading="lazy"
                />
                <div className="cart-sidebar-item-info">
                  <strong>{line.product.title}</strong>
                  <span className="cart-sidebar-item-price">
                    {money(line.product.price_cents, line.product.currency)}
                  </span>
                </div>
                <div className="cart-sidebar-item-actions">
                  <div className="cart-qty-stepper">
                    <button
                      type="button"
                      aria-label={`Decrease ${line.product.title}`}
                      onClick={() => onDecrement(line.product.sku)}
                    >
                      <Minus size={11} />
                    </button>
                    <span>{line.quantity}</span>
                    <button
                      type="button"
                      aria-label={`Increase ${line.product.title}`}
                      disabled={line.quantity >= line.product.stock}
                      onClick={() => onIncrement(line.product.sku)}
                    >
                      <Plus size={11} />
                    </button>
                  </div>
                  <button
                    type="button"
                    className="cart-item-trash"
                    aria-label={`Remove ${line.product.title}`}
                    onClick={() => onRemove(line.product.sku)}
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Decline warning inside cart if intercepted */}
      {decline ? (
        <div className="cart-decline-box" role="alert">
          <div className="cart-decline-header">
            <X size={14} className="decline-icon" />
            <strong>Declined: {decline.reason}</strong>
          </div>
          <p>Cart total exceeds active session limit. Increase spending limit to checkout.</p>
          <button type="button" className="cart-decline-cta" onClick={onOpenLimit}>
            Change limit
          </button>
        </div>
      ) : null}

      {/* Cart Summary & Checkout CTA */}
      {lines.length > 0 ? (
        <div className="cart-sidebar-footer">
          <div className="cart-subtotal-row">
            <span>Total</span>
            <strong>{money(totalCents, currency)}</strong>
          </div>
          <button
            type="button"
            className="primary-button cart-sidebar-checkout"
            disabled={busy || lines.length === 0}
            onClick={onCheckout}
          >
            <ShoppingBag size={15} />
            <span>{busy ? "Preparing preview…" : `Checkout · ${money(totalCents, currency)}`}</span>
          </button>
        </div>
      ) : null}

      {/* Collapsible Visa Purchase Protection at bottom */}
      <div className="cart-protection-accordion">
        <button
          type="button"
          className="cart-protection-toggle"
          onClick={() => setProtectionOpen((open) => !open)}
          aria-expanded={protectionOpen}
        >
          <div className="cart-protection-toggle-label">
            <ShieldCheck size={16} />
            <span>Visa Purchase Protection</span>
          </div>
          <div className="cart-protection-toggle-state">
            <span className="protection-badge">{trustEvents.length} events</span>
            {protectionOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </div>
        </button>

        {protectionOpen ? (
          <div className="cart-protection-content">
            <TrustRail stage={stage} budgetCents={budgetCents} events={trustEvents} isCollapsibleContent />
          </div>
        ) : null}
      </div>
    </aside>
  );
}
