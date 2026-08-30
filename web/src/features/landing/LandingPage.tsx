import React, { useState } from "react";
import {
  Zap,
  Play,
  ArrowRight,
  ShieldCheck,
  Sparkles,
  Settings2,
  Lock,
  ChevronDown,
  ShoppingCart,
  MoreHorizontal,
  Send,
  FileSpreadsheet,
  Cpu,
  Code2,
  ShoppingBag,
  Check,
} from "lucide-react";
import "./landing.css";
import { VisaBrandMark } from "./VisaBrandMark";

interface LandingPageProps {
  onNavigate?: (path: string) => void;
}

export const LandingPage: React.FC<LandingPageProps> = ({ onNavigate }) => {
  const [selectedConcern, setSelectedConcern] = useState<string>("Dryness");
  const [selectedProducts, setSelectedProducts] = useState<string[]>([
    "Gentle Gel Cleanser",
    "Hydra Calm Serum",
  ]);

  const handleNav = (e: React.MouseEvent<HTMLAnchorElement>, path: string) => {
    e.preventDefault();
    if (onNavigate) {
      onNavigate(path);
    } else {
      window.location.href = path;
    }
  };

  const toggleProduct = (name: string) => {
    setSelectedProducts((prev) =>
      prev.includes(name) ? prev.filter((p) => p !== name) : [...prev, name]
    );
  };

  return (
    <div className="landing-root">
      {/* 1. Header / Navbar */}
      <header className="landing-nav">
        <div className="landing-nav-inner">
          <div className="landing-brand">
            <a
              href="/"
              onClick={(e) => handleNav(e, "/")}
              className="landing-logo"
            >
              <span>Sway</span>
            </a>
            <span className="landing-powered-tag">Powered by Visa</span>
          </div>

          <nav className="landing-menu" aria-label="Main Navigation">
            <div className="nav-dropdown-wrapper">
              <button className="nav-link nav-dropdown-btn">
                Product <ChevronDown size={14} className="chevron-icon" />
              </button>
            </div>
            <a
              href="#how-it-works"
              className="nav-link"
              onClick={(e) => {
                e.preventDefault();
                document
                  .getElementById("how-it-works")
                  ?.scrollIntoView({ behavior: "smooth" });
              }}
            >
              How it works
            </a>
            <a
              href="/admin"
              className="nav-link"
              onClick={(e) => handleNav(e, "/admin")}
            >
              For merchants
            </a>
            <a href="#pricing" className="nav-link">
              Pricing
            </a>
            <div className="nav-dropdown-wrapper">
              <button className="nav-link nav-dropdown-btn">
                Resources <ChevronDown size={14} className="chevron-icon" />
              </button>
            </div>
          </nav>

          <div className="landing-nav-actions">
            <a
              href="/admin"
              className="btn-ghost"
              onClick={(e) => handleNav(e, "/admin")}
            >
              Log in
            </a>
            <a
              href="/admin"
              className="btn-primary-dark"
              onClick={(e) => handleNav(e, "/admin")}
            >
              Get started in 90 seconds
            </a>
          </div>
        </div>
      </header>

      {/* 2. Hero Section */}
      <main>
        <section className="landing-hero-section">
          <div className="landing-container hero-grid">
            {/* Left Hero Content */}
            <div className="hero-content">
              <div className="hero-pill-badge">
                <Zap size={14} className="badge-zap" />
                <span>The 90-Second Conversational Commerce Platform</span>
              </div>

              <h1 className="hero-headline">
                Turn conversations <br />
                into <span className="hero-highlight-serif">trusted</span> sales.
              </h1>

              <p className="hero-subtitle">
                Sway is a turnkey platform that lets merchants deploy AI
                shopping agents in under 90 seconds—so shoppers can discover,
                decide, and pay in a single conversation, backed by Visa’s trust.
              </p>

              <div className="hero-cta-group">
                <a
                  href="/admin"
                  className="btn-cta-primary"
                  onClick={(e) => handleNav(e, "/admin")}
                >
                  Get started in 90 seconds
                  <ArrowRight size={17} />
                </a>
                <a
                  href="/storefront?merchant=m_mysa"
                  className="btn-cta-secondary"
                  onClick={(e) => handleNav(e, "/storefront?merchant=m_mysa")}
                >
                  See how it works
                  <span className="play-icon-circle">
                    <Play size={11} fill="currentColor" />
                  </span>
                </a>
              </div>

              <div className="hero-feature-badges">
                <div className="feature-item">
                  <Settings2 size={16} className="feature-icon" />
                  <span>No engineering required</span>
                </div>
                <div className="feature-item">
                  <Sparkles size={16} className="feature-icon" />
                  <span>Pre-built category intelligence</span>
                </div>
                <div className="feature-item">
                  <ShieldCheck size={16} className="feature-icon" />
                  <span>Visa-secure payments in chat</span>
                </div>
              </div>
            </div>

            {/* Right Hero Mockup Card */}
            <div className="hero-mockup-wrapper">
              <div className="hero-card-frame">
                {/* Left Pane: Chat Experience */}
                <div className="mockup-chat-pane">
                  <div className="mockup-chat-header">
                    <div>
                      <h2 className="mockup-store-title">Mysa Skin</h2>
                      <div className="mockup-agent-status">
                        <span className="status-dot"></span>
                        <span>AI Shopping Assistant</span>
                      </div>
                    </div>
                    <div className="mockup-header-tools">
                      <div className="mockup-cart-badge">
                        <ShoppingCart size={13} />
                        <span>2</span>
                      </div>
                      <button className="mockup-menu-btn" aria-label="Options">
                        <MoreHorizontal size={15} />
                      </button>
                    </div>
                  </div>

                  <div className="mockup-chat-body">
                    {/* Agent Message */}
                    <div className="mockup-msg-agent">
                      <p>
                        I can help you find gentle, catalog-verified skincare.
                        What is your main concern right now, and is your skin
                        easily sensitive?
                      </p>
                    </div>

                    {/* Quick Reply Chips */}
                    <div className="mockup-chips-row">
                      {["Dryness", "Sensitive skin", "Acne-prone", "Not sure"].map(
                        (chip) => (
                          <button
                            key={chip}
                            className={`mockup-chip ${
                              selectedConcern === chip ? "active" : ""
                            }`}
                            onClick={() => setSelectedConcern(chip)}
                          >
                            {chip}
                          </button>
                        )
                      )}
                    </div>

                    {/* Compare Section */}
                    <div className="mockup-compare-block">
                      <div className="mockup-compare-header">
                        <span className="compare-title">Compare (0-LLM)</span>
                        <a
                          href="/storefront?merchant=m_mysa"
                          className="compare-link"
                          onClick={(e) =>
                            handleNav(e, "/storefront?merchant=m_mysa")
                          }
                        >
                          View details →
                        </a>
                      </div>

                      <div className="mockup-product-grid">
                        {/* Product 1 */}
                        <div
                          className={`mockup-product-item ${
                            selectedProducts.includes("Gentle Gel Cleanser")
                              ? "selected"
                              : ""
                          }`}
                          onClick={() => toggleProduct("Gentle Gel Cleanser")}
                        >
                          <div className="product-checkbox">
                            {selectedProducts.includes("Gentle Gel Cleanser") && (
                              <Check size={11} strokeWidth={3} />
                            )}
                          </div>
                          <div className="product-img-box">
                            <img
                              src="/products/gentle-cloud.png"
                              alt="Gentle Gel Cleanser"
                            />
                          </div>
                          <div className="product-details">
                            <h4>Gentle Gel Cleanser</h4>
                            <div className="price-text">$18.00</div>
                            <div className="rating-text">
                              <span className="star">4.8 ★</span>
                              <span className="count">(128)</span>
                            </div>
                          </div>
                        </div>

                        {/* Product 2 */}
                        <div
                          className={`mockup-product-item ${
                            selectedProducts.includes("Hydra Calm Serum")
                              ? "selected"
                              : ""
                          }`}
                          onClick={() => toggleProduct("Hydra Calm Serum")}
                        >
                          <div className="product-checkbox">
                            {selectedProducts.includes("Hydra Calm Serum") && (
                              <Check size={11} strokeWidth={3} />
                            )}
                          </div>
                          <div className="product-img-box">
                            <img
                              src="/products/niacinamide-serum.png"
                              alt="Hydra Calm Serum"
                            />
                          </div>
                          <div className="product-details">
                            <h4>Hydra Calm Serum</h4>
                            <div className="price-text">$24.00</div>
                            <div className="rating-text">
                              <span className="star">4.9 ★</span>
                              <span className="count">(96)</span>
                            </div>
                          </div>
                        </div>

                        {/* Product 3 */}
                        <div
                          className={`mockup-product-item ${
                            selectedProducts.includes("Daily Moisturizer")
                              ? "selected"
                              : ""
                          }`}
                          onClick={() => toggleProduct("Daily Moisturizer")}
                        >
                          <div className="product-checkbox">
                            {selectedProducts.includes("Daily Moisturizer") && (
                              <Check size={11} strokeWidth={3} />
                            )}
                          </div>
                          <div className="product-img-box">
                            <img
                              src="/products/bright-barrier.png"
                              alt="Daily Moisturizer"
                            />
                          </div>
                          <div className="product-details">
                            <h4>Daily Moisturizer</h4>
                            <div className="price-text">$22.00</div>
                            <div className="rating-text">
                              <span className="star">4.7 ★</span>
                              <span className="count">(154)</span>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Input bar */}
                  <div className="mockup-chat-input">
                    <input
                      type="text"
                      placeholder="Ask about products or routines..."
                      readOnly
                    />
                    <button
                      className="input-send-btn"
                      aria-label="Send message"
                      onClick={() =>
                        (window.location.href = "/storefront?merchant=m_mysa")
                      }
                    >
                      <Send size={13} />
                    </button>
                  </div>
                </div>

                {/* Right Pane: Secure Checkout / Trust Rail */}
                <div className="mockup-rail-pane">
                  <div className="mockup-rail-header">
                    <span className="rail-heading">Secure checkout</span>
                    <VisaBrandMark className="visa-brand-mark--rail" />
                  </div>

                  <div className="mockup-rail-steps">
                    {/* Step 1 */}
                    <div className="rail-step is-complete">
                      <div className="rail-marker">
                        <Check size={11} strokeWidth={3} />
                      </div>
                      <div className="rail-step-text">
                        <strong>Catalog verified</strong>
                        <p>Prices, stock, and facts locked</p>
                      </div>
                    </div>

                    {/* Step 2 */}
                    <div className="rail-step is-complete">
                      <div className="rail-marker">
                        <Check size={11} strokeWidth={3} />
                      </div>
                      <div className="rail-step-text">
                        <div className="step-title-split">
                          <strong>Your limit</strong>
                          <span className="change-link">Change ⌵</span>
                        </div>
                        <p className="limit-val">$100.00</p>
                      </div>
                    </div>

                    {/* Step 3 */}
                    <div className="rail-step">
                      <div className="rail-marker empty"></div>
                      <div className="rail-step-text">
                        <strong>Your cart</strong>
                        <p>2 items • $42.00</p>
                      </div>
                    </div>

                    {/* Step 4 */}
                    <div className="rail-step">
                      <div className="rail-marker empty"></div>
                      <div className="rail-step-text">
                        <strong>Your confirmation</strong>
                        <p>Exact total, shipping, payment</p>
                      </div>
                    </div>

                    {/* Step 5 */}
                    <div className="rail-step">
                      <div className="rail-marker empty"></div>
                      <div className="rail-step-text">
                        <strong>Bank verification</strong>
                        <p>Visa Secure (OTP)</p>
                      </div>
                    </div>

                    {/* Step 6 */}
                    <div className="rail-step">
                      <div className="rail-marker empty"></div>
                      <div className="rail-step-text">
                        <strong>Agent verified</strong>
                        <p>TAP signature & nonce</p>
                      </div>
                    </div>

                    {/* Step 7 */}
                    <div className="rail-step">
                      <div className="rail-marker empty"></div>
                      <div className="rail-step-text">
                        <strong>Payment</strong>
                        <p>Complete</p>
                      </div>
                    </div>
                  </div>

                  <div className="mockup-rail-footer">
                    <Lock size={12} />
                    <span>Secure • Private • Visa protected</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* 3. Built on Visa Trust Marquee */}
        <section className="landing-marquee-section">
          <div className="landing-container">
            <h3 className="marquee-caption">
              Built on Visa's trust and payment network
            </h3>
            <div className="marquee-grid">
              <div className="marquee-card">
                <ShieldCheck size={20} className="marquee-icon" />
                <span>Visa 3DS & Bank Verification</span>
              </div>
              <div className="marquee-card">
                <FileSpreadsheet size={20} className="marquee-icon" />
                <span>AP2 Verifiable Mandate Chain</span>
              </div>
              <div className="marquee-card">
                <Code2 size={20} className="marquee-icon" />
                <span>RFC 9421 (TAP) Message Signatures</span>
              </div>
              <div className="marquee-card">
                <Zap size={20} className="marquee-icon" />
                <span>Exact Human Consent</span>
              </div>
              <div className="marquee-card">
                <Sparkles size={20} className="marquee-icon" />
                <span>No Hallucinations. Only Facts.</span>
              </div>
              <div className="marquee-card marquee-visa-brand">
                <VisaBrandMark className="visa-brand-mark--marquee" />
                <div className="visa-tagline">
                  <strong>Global standards.</strong>
                  <span>Local trust.</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* 4. From Catalog to AI Commerce in 90 Seconds */}
        <section id="how-it-works" className="landing-steps-section">
          <div className="landing-container steps-layout">
            <div className="steps-header-col">
              <h2 className="steps-main-title">
                From catalog to AI commerce <br />
                in <span className="highlight-serif-green">90 seconds</span>
              </h2>
              <p className="steps-main-desc">
                No AI team. No complex setup. Just upload and go.
              </p>
              <a
                href="/admin"
                className="steps-guide-link"
                onClick={(e) => handleNav(e, "/admin")}
              >
                See full onboarding guide →
              </a>
            </div>

            <div className="steps-flow-grid">
              {/* Step 1 */}
              <div className="step-workflow-card">
                <div className="step-badge-num">1</div>
                <div className="step-icon-box">
                  <FileSpreadsheet size={24} />
                </div>
                <h3>Upload your catalog</h3>
                <p>
                  Drag & drop your .csv, .xlsx, or .json file. We auto-map and
                  validate.
                </p>
              </div>

              <div className="step-arrow-connector">····&gt;</div>

              {/* Step 2 */}
              <div className="step-workflow-card">
                <div className="step-badge-num">2</div>
                <div className="step-icon-box">
                  <Cpu size={24} />
                </div>
                <h3>AI ready in seconds</h3>
                <p>
                  Sway builds your product knowledge, taxonomy, and guardrails
                  instantly.
                </p>
              </div>

              <div className="step-arrow-connector">····&gt;</div>

              {/* Step 3 */}
              <div className="step-workflow-card">
                <div className="step-badge-num">3</div>
                <div className="step-icon-box">
                  <Code2 size={24} />
                </div>
                <h3>Add in one line</h3>
                <p>
                  Paste a single &lt;script&gt; to your site or get a hosted link
                  & QR code.
                </p>
              </div>

              <div className="step-arrow-connector">····&gt;</div>

              {/* Step 4 */}
              <div className="step-workflow-card">
                <div className="step-badge-num">4</div>
                <div className="step-icon-box">
                  <ShoppingBag size={24} />
                </div>
                <h3>Start selling in chat</h3>
                <p>
                  Shoppers discover, compare, and pay—without leaving the
                  conversation.
                </p>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="landing-footer">
        <div className="landing-container landing-footer-inner">
          <div className="footer-brand-side">
            <span className="footer-logo">Sway</span>
            <p>
              Conversational commerce infrastructure for the agentic web.
              Powered by Visa.
            </p>
          </div>
          <div className="footer-links-side">
            <a href="/admin" onClick={(e) => handleNav(e, "/admin")}>
              Merchant Portal
            </a>
            <a
              href="/storefront?merchant=m_mysa"
              onClick={(e) => handleNav(e, "/storefront?merchant=m_mysa")}
            >
              Shopper Demo
            </a>
            <a href="/widget-demo.html">Widget Demo</a>
            <a href="http://localhost:8000/docs" target="_blank" rel="noreferrer">
              API Specs
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
};
