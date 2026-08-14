import { Link } from "react-router-dom";
import "./LandingPage.css";

const TICKER_ITEMS = [
  "Built for businesses",
  "OCR-powered extraction",
  "Instant KYC verification",
  "Facial verification",
  "Signature matching",
];

const DIFFERENCE_CARDS = [
  {
    n: "01",
    title: "We read the room.",
    body: "Upload your company documents once. Our OCR engine extracts the details, so nobody has to re-key a thing.",
    icon: <path d="M8 3h8l4 4v14H8V3z M16 3v4h4 M11 13h6 M11 17h6" />,
  },
  {
    n: "02",
    title: "We verify the people.",
    body: "KYC and facial verification happen in the same guided flow, with every check visible to your team.",
    icon: <path d="M12 4a4 4 0 100 8 4 4 0 000-8z M6 21a6 6 0 0112 0" />,
  },
  {
    n: "03",
    title: "We connect the dots.",
    body: "Signature matching cross-checks submitted documents for a complete, consistent picture of your business.",
    icon: <path d="M6 18l6-12 6 12 M9 14h6" />,
  },
];

const TEAM_STATS = [
  {
    tone: "light",
    icon: <path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6l7-3z" />,
    title: "A clear yes.",
    body: "See what's verified, what's next and where to help — at a glance.",
    tag: "Application status",
  },
  {
    tone: "dark",
    icon: <path d="M12 3l1.8 4.2L18 9l-4.2 1.8L12 15l-1.8-4.2L6 9l4.2-1.8L12 3z" />,
    title: "More momentum.",
    big: "30",
    bigLabel: "MINUTES\nOR LESS",
    body: "Move from incorporation to your first payment before the week disappears.",
  },
];

const TRUST_ITEMS = [
  {
    n: "01",
    title: "Built for sensitive information",
    body: "Your business data is handled with the care and controls you expect from a bank.",
  },
  {
    n: "02",
    title: "Decisions you can stand behind",
    body: "Every check is designed to create a clear record for your team and your compliance partners.",
  },
  {
    n: "03",
    title: "A flow people can actually finish",
    body: "Simple language, guided steps and fewer handoffs mean fewer applications stall halfway.",
  },
];

function Icon({ children, className = "" }) {
  return (
    <svg
      className={`bp-icon ${className}`}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {children}
    </svg>
  );
}

function Header() {
  return (
    <header className="bp-header">
      <Link to="/" className="bp-wordmark">
        <span className="bp-logo-dot" />
        Bank of Penta
      </Link>
      <nav className="bp-nav">
        <a href="#how-it-works">How it works</a>
        <a href="#for-finance-teams">For finance teams</a>
        <a href="#trust">Trust &amp; security</a>
      </nav>
      <div className="bp-header-actions">
        <Link to="/login" className="bp-link">Log in</Link>
        <Link to="/onboarding" className="bp-btn bp-btn-primary">
          Create account <span aria-hidden>→</span>
        </Link>
      </div>
    </header>
  );
}

function Hero() {
  return (
    <section className="bp-hero">
      <div className="bp-hero-copy">
        <p className="bp-eyebrow"><span className="bp-eyebrow-rule" />Business banking, in motion</p>
        <h1 className="bp-hero-title">
          Ready before <em>the paperwork</em> gets cold.
        </h1>
        <p className="bp-hero-lede">
          Bank of Penta helps ambitious businesses onboard, verify and start
          banking in under 30 minutes — not two to seven business days.
        </p>
        <div className="bp-hero-actions">
          <Link to="/onboarding" className="bp-btn bp-btn-primary bp-btn-lg">
            Create your account <span aria-hidden>→</span>
          </Link>
          <a href="#how-it-works" className="bp-btn bp-btn-text">
            See how it works <span aria-hidden>↘</span>
          </a>
        </div>
        <div className="bp-social-proof">
          <div className="bp-avatars">
            <span>A</span><span>M</span><span>S</span>
          </div>
          <p>Finance teams at fast-moving companies are already moving.</p>
        </div>
      </div>

      <div className="bp-hero-card-wrap">
        <div className="bp-toast">
          <Icon className="bp-toast-icon"><path d="M5 13l4 4L19 7" /></Icon>
          <div>
            <p className="bp-toast-title">KYC approved</p>
            <p className="bp-toast-time">just now</p>
          </div>
        </div>

        <div className="bp-status-card">
          <div className="bp-status-card-head">
            <span className="bp-status-card-label">New business account</span>
            <span className="bp-live-badge">Live</span>
          </div>
          <p className="bp-status-card-sub">Application progress</p>
          <div className="bp-status-card-progress-row">
            <span className="bp-status-card-count">04<span>/04</span></span>
            <span className="bp-status-card-time">28 min left</span>
          </div>
          <div className="bp-progress-track">
            <div className="bp-progress-fill" style={{ width: "92%" }} />
          </div>
          <ul className="bp-checklist">
            <li>
              <span className="bp-check-dot bp-check-done"><Icon><path d="M5 13l4 4L19 7" /></Icon></span>
              Company registration <span className="bp-check-state">Verified</span>
            </li>
            <li>
              <span className="bp-check-dot bp-check-done"><Icon><path d="M5 13l4 4L19 7" /></Icon></span>
              Ownership structure <span className="bp-check-state">Verified</span>
            </li>
            <li>
              <span className="bp-check-dot bp-check-done"><Icon><path d="M5 13l4 4L19 7" /></Icon></span>
              Director identity <span className="bp-check-state">Verified</span>
            </li>
            <li>
              <span className="bp-check-dot bp-check-ready" />
              Signature comparison <span className="bp-check-state bp-check-state-ready">Ready</span>
            </li>
          </ul>
        </div>
      </div>
    </section>
  );
}

function Marquee() {
  const items = [...TICKER_ITEMS, ...TICKER_ITEMS];
  return (
    <div className="bp-marquee">
      <span className="bp-marquee-label">Built for momentum</span>
      <div className="bp-marquee-track">
        {items.map((item, i) => (
          <span key={i} className="bp-marquee-item">
            {item} <span className="bp-marquee-dot" />
          </span>
        ))}
      </div>
    </div>
  );
}

function DifferenceSection() {
  return (
    <section id="how-it-works" className="bp-section">
      <p className="bp-eyebrow">01 / The difference</p>
      <div className="bp-section-head">
        <h2>Banking that keeps its word.</h2>
        <p>
          The old process was built around waiting. Penta is built around
          getting on with it. We turn the evidence your company already has
          into a clear, confident decision.
        </p>
      </div>
      <div className="bp-card-grid">
        {DIFFERENCE_CARDS.map((c) => (
          <div className="bp-diff-card" key={c.n}>
            <div className="bp-diff-card-top">
              <span className="bp-diff-card-n">{c.n}</span>
              <span className="bp-diff-card-icon"><Icon>{c.icon}</Icon></span>
            </div>
            <h3>{c.title}</h3>
            <p>{c.body}</p>
            <span className="bp-arrow" aria-hidden>→</span>
          </div>
        ))}
      </div>
    </section>
  );
}

function ForTeamsSection() {
  return (
    <section id="for-finance-teams" className="bp-section bp-section-dark">
      <div className="bp-team-grid">
        <div>
          <p className="bp-eyebrow bp-eyebrow-gold">02 / For the people doing the work</p>
          <h2>Your team has better things to do.</h2>
          <p className="bp-team-lede">
            Give finance a clear path from "we're setting up" to "we're
            operational." No chasing. No mystery status. No inbox archaeology.
          </p>
          <a href="#contact" className="bp-btn bp-btn-gold">
            Talk to our team <span aria-hidden>→</span>
          </a>
        </div>
        <div className="bp-team-cards">
          {TEAM_STATS.map((s) => (
            <div className={`bp-team-stat bp-team-stat-${s.tone}`} key={s.title}>
              <span className="bp-team-stat-icon"><Icon>{s.icon}</Icon></span>
              <h3>{s.title}</h3>
              {s.big && (
                <p className="bp-team-stat-big">
                  {s.big}<span>{s.bigLabel}</span>
                </p>
              )}
              <p>{s.body}</p>
              {s.tag && <span className="bp-tag"><span className="bp-tag-dot" />{s.tag}</span>}
            </div>
          ))}
          <div className="bp-team-flow">
            <div className="bp-team-flow-head">
              <span className="bp-eyebrow bp-eyebrow-gold">Everything in one flow</span>
              <span className="bp-flow-arrow" aria-hidden>↗</span>
            </div>
            <h3>Operational calm, by design.</h3>
            <div className="bp-flow-tags">
              <span><span className="bp-tag-dot" />Documents extracted</span>
              <span><span className="bp-tag-dot" />KYC complete</span>
              <span><span className="bp-tag-dot" />Signatures matched</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function TrustSection() {
  return (
    <section id="trust" className="bp-section bp-section-trust">
      <p className="bp-eyebrow">03 / Trust is a feature</p>
      <div className="bp-trust-grid">
        <h2>Fast does not mean loose.</h2>
        <ul className="bp-trust-list">
          {TRUST_ITEMS.map((t) => (
            <li key={t.n}>
              <div className="bp-trust-item-head">
                <span className="bp-trust-n">{t.n}</span>
                <span className="bp-trust-check"><Icon><path d="M5 13l4 4L19 7" /></Icon></span>
              </div>
              <h3>{t.title}</h3>
              <p>{t.body}</p>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

function ClosingCTA() {
  return (
    <section className="bp-closing">
      <div className="bp-closing-ring" aria-hidden />
      <p className="bp-eyebrow bp-eyebrow-center">A better starting line</p>
      <h2>
        Get your business <em>moving.</em>
      </h2>
      <p>Set up with the confidence of a partner who understands what's at stake.</p>
      <div className="bp-closing-actions">
        <Link to="/onboarding" className="bp-btn bp-btn-primary bp-btn-lg">
          Create your account <span aria-hidden>→</span>
        </Link>
        <a href="#contact" className="bp-btn bp-btn-outline">Request a conversation</a>
      </div>
    </section>
  );
}

function Footer() {
  return (
    <footer className="bp-footer">
      <div className="bp-footer-top">
        <div>
          <div className="bp-wordmark bp-wordmark-light">
            <span className="bp-logo-dot bp-logo-dot-gold" />
            Bank of Penta
          </div>
          <p>A calmer, faster way to get your business banking started.</p>
        </div>
        <nav className="bp-footer-links">
          <a href="#how-it-works">How it works</a>
          <a href="#trust">Trust &amp; security</a>
          <a href="#contact">Contact us</a>
        </nav>
      </div>
      <div className="bp-footer-bottom">
        <span>© {new Date().getFullYear()} Bank of Penta</span>
        <span>Business banking, in motion.</span>
      </div>
    </footer>
  );
}

export default function LandingPage() {
  return (
    <div className="bp-page">
      <Header />
      <Hero />
      <Marquee />
      <DifferenceSection />
      <ForTeamsSection />
      <TrustSection />
      <ClosingCTA />
      <Footer />
    </div>
  );
}