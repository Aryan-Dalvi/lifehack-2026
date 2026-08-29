import {
  ArrowRight,
  Bell,
  Boxes,
  ChevronDown,
  ChevronRight,
  Code2,
  Download,
  ExternalLink,
  Infinity as InfinityIcon,
  LayoutGrid,
  ListChecks,
  LoaderCircle,
  MessageSquareText,
  MoreVertical,
  Plus,
  QrCode,
  Search,
  Settings,
  ShieldCheck,
  Sparkles,
  Store,
  TrendingUp,
  Users,
  Wand2,
} from "lucide-react";
import { type FormEvent, useEffect, useMemo, useState } from "react";
import { api, getMerchantKey, money } from "../../api";
import type { Insights, Summary, Task } from "./insights";
import "./dashboard.css";

const WINDOWS = [
  { days: 30, label: "Last 30 days" },
  { days: 14, label: "Last 14 days" },
  { days: 7, label: "Last 7 days" },
];

const TABS = [
  { key: "overview", label: "Overview" },
  { key: "customers", label: "Customers" },
  { key: "products", label: "Products" },
  { key: "tasks", label: "Tasks" },
  { key: "analytics", label: "Analytics" },
] as const;

type TabKey = (typeof TABS)[number]["key"];

/** The assistant's four shortcuts. Each opens one report; none of them free-form the numbers. */
const SHORTCUTS = [
  { scope: "revenue", label: "Revenue summary", icon: TrendingUp, tone: "violet" },
  { scope: "customers", label: "Customer health", icon: Users, tone: "teal" },
  { scope: "catalog", label: "Catalog check", icon: Boxes, tone: "amber" },
  { scope: "tasks", label: "What to fix first", icon: ListChecks, tone: "rose" },
] as const;

const SOURCE_LABELS: Record<string, string> = {
  deterministic: "Computed from your data",
  deterministic_failover: "Computed from your data",
  model_rephrased_deterministic_facts: "Your figures, reworded by the assistant",
};

/**
 * Revenue as a dot column per day: one dot is a fixed slice of money, so height is
 * countable rather than estimated. Actual days are solid, the forecast is hollow, and the
 * best day is called out - the three things a merchant actually looks for in a trend.
 */
function RevenueChart({ series }: { series: Insights["revenue_series"] }) {
  const rows = 9;
  const ceiling = Math.max(
    ...series.points.map((point) => point.actual_cents ?? point.projected_cents ?? 0),
    1,
  );
  // Three gridlines above zero, each landing on a round amount: an axis a merchant has to
  // read as 333.33 is an axis they stop reading.
  const target = ceiling / 3;
  const magnitude = Math.pow(10, Math.floor(Math.log10(target)));
  const tick =
    [1, 1.5, 2, 2.5, 3, 4, 5, 7.5, 10]
      .map((multiple) => multiple * magnitude)
      .find((candidate) => candidate >= target) ?? magnitude * 10;
  const axisMax = tick * 3;
  const peakDate = series.peak?.date;

  return (
    <div className="crm-chart">
      <div className="crm-chart-axis">
        {[3, 2, 1, 0].map((mark) => (
          <span key={mark}>{money((axisMax / 3) * mark, series.currency).replace(/\.00$/, "")}</span>
        ))}
      </div>
      <div className="crm-chart-plot">
        <div className="crm-chart-columns">
          {series.points.map((point) => {
            const value = point.actual_cents ?? point.projected_cents ?? 0;
            const filled = value === 0 ? 0 : Math.max(1, Math.round((value / axisMax) * rows));
            const isPeak = point.date === peakDate;
            return (
              <div
                className={`crm-chart-column${isPeak ? " is-peak" : ""}`}
                key={point.date}
                title={`${point.label}: ${money(value, series.currency)}${point.is_forecast ? " projected" : ""}`}
              >
                {isPeak ? (
                  <b className="crm-chart-callout" style={{ bottom: `${(filled / rows) * 100}%` }}>
                    {money(value, series.currency).replace(/\.00$/, "")}
                  </b>
                ) : null}
                {Array.from({ length: rows }).map((_, row) => (
                  <i
                    key={row}
                    className={
                      row >= rows - filled
                        ? point.is_forecast
                          ? "is-forecast"
                          : isPeak
                            ? "is-peak"
                            : "is-actual"
                        : "is-empty"
                    }
                  />
                ))}
              </div>
            );
          })}
        </div>
        <div className="crm-chart-dates">
          {series.points.map((point, index) => (
            <span
              key={point.date}
              className={point.date === peakDate ? "is-peak" : ""}
              data-show={point.date === peakDate || index % 5 === 0 ? "yes" : "no"}
            >
              {point.label}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

/** One row of open work. The rail and the full Tasks tab render the same thing. */
function TaskItem({ task, onOpen }: { task: Task; onOpen: (path: string) => void }) {
  return (
    <li>
      <a
        href={task.action}
        onClick={(event) => {
          // In-app destinations stay in the app; an anchor on this page is left alone.
          if (task.action.startsWith("/")) {
            event.preventDefault();
            onOpen(task.action);
          }
        }}
      >
        <span className="crm-task-dot" data-severity={task.severity} />
        <span className="crm-task-body">
          <b>
            {task.title}
            <em>{task.chip}</em>
            {task.progress ? (
              <em className="is-progress">
                <Sparkles size={11} /> {task.progress.done}/{task.progress.total} {task.progress.noun}
              </em>
            ) : null}
          </b>
          <small>{task.detail}</small>
        </span>
        <ChevronRight size={16} />
      </a>
    </li>
  );
}

function StatusPill({ status, label }: { status: string; label: string }) {
  return <span className={`crm-pill crm-pill--${status}`}>{label}</span>;
}

function CustomerTable({
  insights,
  rows,
  activeTab,
  onTab,
  full,
}: {
  insights: Insights;
  rows: Insights["customers"];
  activeTab: string;
  onTab: (key: string) => void;
  full: boolean;
}) {
  return (
    <section className="crm-card crm-table-card" id="customers">
      <header className="crm-table-head">
        <h2>{full ? "All customers" : "Manage customers"}</h2>
        <Search size={16} aria-hidden />
      </header>
      <div className="crm-tabs">
        <button
          type="button"
          className={activeTab === "all" ? "is-active" : ""}
          onClick={() => onTab("all")}
        >
          All <b>{insights.customers.length}</b>
        </button>
        {insights.customer_tabs.map((tab) => (
          <button
            type="button"
            key={tab.key}
            className={activeTab === tab.key ? "is-active" : ""}
            onClick={() => onTab(tab.key)}
          >
            {tab.label} {tab.count ? <b>{tab.count}</b> : null}
          </button>
        ))}
      </div>
      <div className="crm-table-scroll">
        <table className="crm-table">
          <thead>
            <tr>
              <th>Customer</th>
              <th>Last basket</th>
              <th>What they asked for</th>
              <th>Last seen</th>
              <th>Value</th>
              <th>Status</th>
              <th aria-label="Actions" />
            </tr>
          </thead>
          <tbody>
            {rows.map((customer) => (
              <tr key={customer.consumer_id}>
                <td>
                  <div className="crm-person">
                    <i className={customer.is_anonymous ? "is-guest" : ""}>{customer.initials}</i>
                    <span>
                      {customer.name}
                      <small>@{customer.handle}</small>
                    </span>
                  </div>
                </td>
                <td>
                  {customer.last_item ?? "Browsed only"}
                  <small>
                    {customer.orders} order{customer.orders === 1 ? "" : "s"}
                  </small>
                </td>
                <td className="crm-note">{customer.note}</td>
                <td>{customer.last_activity_label}</td>
                <td className="crm-value">
                  {money(customer.value_cents, insights.merchant.currency)}
                  <small>{customer.value_kind}</small>
                </td>
                <td>
                  <StatusPill status={customer.status} label={customer.status_label} />
                </td>
                <td>
                  <MoreVertical size={15} aria-hidden />
                </td>
              </tr>
            ))}
            {rows.length === 0 ? (
              <tr>
                <td colSpan={7} className="crm-empty">
                  No customers in this group yet.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function MerchantDashboard({ onNavigate }: { onNavigate?: (path: string) => void }) {
  const [insights, setInsights] = useState<Insights | null>(null);
  const [days, setDays] = useState(30);
  const [tab, setTab] = useState<TabKey>("overview");
  const [customerTab, setCustomerTab] = useState("all");
  const [summary, setSummary] = useState<Summary | null>(null);
  const [asking, setAsking] = useState(false);
  const [question, setQuestion] = useState("");
  const [error, setError] = useState<string | null>(null);
  const merchantKey = getMerchantKey();

  useEffect(() => {
    if (!merchantKey) {
      onNavigate?.("/admin/setup");
      return;
    }
    let live = true;
    api<Insights>(`/merchant/m_mysa/insights?days=${days}`)
      .then((data) => {
        if (!live) return;
        // The dashboard is the other side of onboarding. A draft store has no trading to
        // report and one screen left to finish, so send it back there.
        if (data.merchant.status !== "published") onNavigate?.("/admin/setup");
        else setInsights(data);
      })
      .catch((requestError: Error) => live && setError(requestError.message));
    return () => {
      live = false;
    };
  }, [days, merchantKey, onNavigate]);

  const ask = async (payload: { question?: string; scope?: string }) => {
    if (!insights) return;
    setAsking(true);
    setError(null);
    try {
      setSummary(
        await api<Summary>(`/merchant/${insights.merchant.merchant_id}/insights/summary`, {
          method: "POST",
          body: JSON.stringify({ ...payload, days }),
        }),
      );
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "That report could not be built.");
    } finally {
      setAsking(false);
    }
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!question.trim()) return;
    void ask({ question: question.trim() });
    setQuestion("");
  };

  const openTask = (path: string) => {
    if (onNavigate) onNavigate(path);
    else globalThis.location.assign(path);
  };

  const visibleCustomers = useMemo(() => {
    if (!insights) return [];
    if (customerTab === "all") return insights.customers;
    return insights.customers.filter((customer) => customer.status === customerTab);
  }, [insights, customerTab]);

  if (!insights) {
    return (
      <main className="crm-loading">
        {error ? (
          <div className="crm-loading-error" role="alert">
            <p>{error}</p>
            <a href="/admin/setup">Back to store setup</a>
          </div>
        ) : (
          <>
            <LoaderCircle className="spin" /> Loading your dashboard…
          </>
        )}
      </main>
    );
  }

  const { merchant, kpis, window: period, tasks, scorecards, activity, catalog } = insights;
  const storefront = `/storefront?merchant=${merchant.merchant_id}`;

  return (
    <div className="crm-shell">
      <div className="crm-window">
        <header className="crm-topbar">
          <a className="crm-brand" href="/admin">
            <i>
              <InfinityIcon size={17} strokeWidth={2.4} />
            </i>
            Sway
          </a>
          <div className="crm-channels" aria-label="Live channels">
            <a href={storefront} className="crm-channel crm-channel--store" title="Hosted storefront">
              <Store size={14} />
            </a>
            <a href="/admin/setup#deploy" className="crm-channel crm-channel--widget" title="Website widget">
              <Code2 size={14} />
            </a>
            <a href="/admin/setup#deploy" className="crm-channel crm-channel--qr" title="Storefront QR code">
              <QrCode size={14} />
            </a>
            <a href="/admin/setup#deploy" className="crm-channel crm-channel--add" title="Add a channel">
              <Plus size={14} />
            </a>
          </div>
          <nav className="crm-nav" aria-label="Dashboard sections">
            {TABS.map((item) => (
              <button
                type="button"
                key={item.key}
                className={tab === item.key ? "is-active" : ""}
                onClick={() => setTab(item.key)}
              >
                {item.label}
              </button>
            ))}
          </nav>
          <div className="crm-actions">
            <a href="/admin/setup" title="Store setup">
              <Settings size={18} />
            </a>
            <button type="button" className="crm-bell" title={`${tasks.length} tasks need attention`}>
              <Bell size={18} />
              {tasks.length ? <i /> : null}
            </button>
            <span className="crm-avatar" title={merchant.name}>
              {merchant.name.slice(0, 1)}
              <i className={merchant.status === "published" ? "is-live" : ""} />
            </span>
          </div>
        </header>

        <div className="crm-body">
          <main className="crm-main">
            {tab === "overview" || tab === "analytics" ? (
              <div className="crm-kpis">
                {kpis.map((kpi) => (
                  <article className="crm-card crm-kpi" key={kpi.key}>
                    <header>
                      <h3>{kpi.label}</h3>
                      <span className={kpi.direction === "down" ? "is-down" : "is-up"}>
                        {kpi.delta_display}
                      </span>
                    </header>
                    <strong>{kpi.display}</strong>
                    <p>
                      Compare <b>{kpi.previous_display}</b> (previous {period.days} days)
                    </p>
                  </article>
                ))}
              </div>
            ) : null}

            {tab === "overview" || tab === "analytics" ? (
              <section className="crm-card crm-analytics">
                <header className="crm-analytics-head">
                  <h2>Revenue analytics</h2>
                  <div className="crm-controls">
                    <span className="crm-select">
                      Earnings <ChevronDown size={14} />
                    </span>
                    <label className="crm-select">
                      <select
                        aria-label="Reporting period"
                        value={days}
                        onChange={(event) => setDays(Number(event.target.value))}
                      >
                        {WINDOWS.map((option) => (
                          <option key={option.days} value={option.days}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                      <ChevronDown size={14} />
                    </label>
                    <a
                      className="crm-icon-button"
                      href={`/api/merchant/${merchant.merchant_id}/insights?days=${days}`}
                      title="Open the underlying report"
                    >
                      <Download size={15} />
                    </a>
                  </div>
                </header>
                <div className="crm-analytics-body">
                  <div className="crm-analytics-side">
                    <ul className="crm-legend">
                      <li>
                        <i className="is-actual" /> Actual
                      </li>
                      <li>
                        <i className="is-forecast" /> Projected
                      </li>
                    </ul>
                    <div className="crm-tip">
                      <InfinityIcon size={15} />
                      <p>{summary?.scope === "revenue" ? summary.summary : insights.insight.text}</p>
                    </div>
                    <button
                      type="button"
                      className="crm-run"
                      onClick={() => void ask({ scope: "revenue" })}
                      disabled={asking}
                    >
                      {asking ? "Working…" : "Run analysis"}
                    </button>
                    <small className="crm-forecast-note">
                      Projection: {insights.revenue_series.forecast.method} ·{" "}
                      {money(insights.revenue_series.forecast.per_day_cents, merchant.currency)} a day.
                    </small>
                  </div>
                  <RevenueChart series={insights.revenue_series} />
                </div>
              </section>
            ) : null}

            {tab === "analytics" ? (
              <section className="crm-card crm-scorecards">
                <header className="crm-table-head">
                  <h2>Performance</h2>
                  <span className="crm-muted">Every figure states what it was divided by.</span>
                </header>
                <div className="crm-scorecard-grid">
                  {scorecards.map((card) => (
                    <article key={card.key}>
                      <h4>{card.label}</h4>
                      <strong>{card.display}</strong>
                      <p>{card.basis}</p>
                      <small>{card.hint}</small>
                    </article>
                  ))}
                </div>
              </section>
            ) : null}

            {tab === "products" ? (
              <section className="crm-card crm-table-card">
                <header className="crm-table-head">
                  <h2>Products</h2>
                  <span className="crm-muted">
                    {catalog.product_count} live · {catalog.in_stock_count} in stock ·{" "}
                    {catalog.with_photo_count} with a photo
                  </span>
                </header>
                <div className="crm-table-scroll">
                  <table className="crm-table">
                    <thead>
                      <tr>
                        <th>Product</th>
                        <th>Units sold</th>
                        <th>Revenue</th>
                        <th>Share of revenue</th>
                      </tr>
                    </thead>
                    <tbody>
                      {insights.top_products.map((product) => {
                        const total = insights.top_products.reduce(
                          (sum, entry) => sum + entry.revenue_cents,
                          0,
                        );
                        const share = total ? Math.round((product.revenue_cents / total) * 100) : 0;
                        return (
                          <tr key={product.sku}>
                            <td>
                              {product.title}
                              <small>{product.sku}</small>
                            </td>
                            <td>{product.units}</td>
                            <td className="crm-value">
                              {money(product.revenue_cents, merchant.currency)}
                            </td>
                            <td>
                              <div className="crm-bar">
                                <i style={{ width: `${share}%` }} />
                                <span>{share}%</span>
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                      {insights.top_products.length === 0 ? (
                        <tr>
                          <td colSpan={4} className="crm-empty">
                            Nothing has sold in this period yet.
                          </td>
                        </tr>
                      ) : null}
                    </tbody>
                  </table>
                </div>
              </section>
            ) : null}

            {tab === "tasks" ? (
              <section className="crm-card crm-table-card">
                <header className="crm-table-head">
                  <h2>Everything needing attention</h2>
                  <span className="crm-muted">Derived from live state, not a checklist.</span>
                </header>
                <ul className="crm-task-list crm-task-list--full">
                  {tasks.map((task) => (
                    <TaskItem key={task.code} task={task} onOpen={openTask} />
                  ))}
                  {tasks.length === 0 ? (
                    <li className="crm-empty">Nothing is waiting on you right now.</li>
                  ) : null}
                </ul>
              </section>
            ) : null}

            {tab === "overview" || tab === "customers" ? (
              <CustomerTable
                insights={insights}
                rows={visibleCustomers}
                activeTab={customerTab}
                onTab={setCustomerTab}
                full={tab === "customers"}
              />
            ) : null}
          </main>

          <aside className="crm-rail">
            <section className="crm-card crm-tasks">
              <header>
                <h2>Priority tasks</h2>
                <button type="button" onClick={() => setTab("tasks")}>
                  See all
                </button>
              </header>
              <ul className="crm-task-list">
                {tasks.slice(0, 4).map((task) => (
                  <TaskItem key={task.code} task={task} onOpen={openTask} />
                ))}
                {tasks.length === 0 ? (
                  <li className="crm-all-clear">
                    <ShieldCheck size={16} /> Stock, photos and checkouts are all clear.
                  </li>
                ) : null}
              </ul>
              <footer className="crm-tasks-foot">
                <LayoutGrid size={13} /> {activity.sessions} conversations · {activity.abandoned_carts}{" "}
                open carts in the last {period.days} days
              </footer>
            </section>

            <section className="crm-card crm-assistant">
              <p className="crm-greeting">Hi, {merchant.name} 👋</p>
              <h2>What would you like summarised?</h2>
              <div className="crm-assistant-source">
                <span className="is-active">
                  <ShieldCheck size={13} /> {SOURCE_LABELS[summary?.source ?? "deterministic"]}
                </span>
              </div>
              <div className="crm-shortcuts">
                {SHORTCUTS.map((shortcut) => (
                  <button
                    type="button"
                    key={shortcut.scope}
                    onClick={() => void ask({ scope: shortcut.scope })}
                    disabled={asking}
                  >
                    <i className={`is-${shortcut.tone}`}>
                      <shortcut.icon size={15} />
                    </i>
                    {shortcut.label}
                  </button>
                ))}
              </div>

              {asking ? (
                <div className="crm-answer is-loading">
                  <LoaderCircle className="spin" size={15} /> Reading your {period.days}-day figures…
                </div>
              ) : summary ? (
                <div className="crm-answer">
                  <h3>
                    {summary.title}
                    <span>{summary.window}</span>
                  </h3>
                  <p>{summary.summary}</p>
                  <ul>
                    {summary.bullets.map((bullet) => (
                      <li key={bullet}>{bullet}</li>
                    ))}
                  </ul>
                </div>
              ) : null}

              <form className="crm-composer" onSubmit={submit}>
                <MessageSquareText size={15} />
                <input
                  value={question}
                  onChange={(event) => setQuestion(event.target.value)}
                  placeholder="Ask about revenue, customers, stock…"
                  aria-label="Ask about your business"
                />
                <button type="submit" disabled={asking || !question.trim()} aria-label="Summarise">
                  <Wand2 size={15} />
                </button>
              </form>
            </section>

            <a className="crm-storefront-link" href={storefront}>
              <ExternalLink size={14} /> Open {merchant.name} storefront
              <ArrowRight size={14} />
            </a>
          </aside>
        </div>

        {error ? (
          <div className="crm-error" role="alert">
            {error}
          </div>
        ) : null}
        <footer className="crm-foot">
          <span>
            {insights.payments.note} Figures are computed from your own orders, carts and sessions.
          </span>
          <a href="/admin/setup">Store setup</a>
        </footer>
      </div>
    </div>
  );
}
