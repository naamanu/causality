const githubUrl = "https://github.com/naamanu/causality";

export default function LandingPage() {
  return (
    <div className="marketing-shell">
      <header className="marketing-nav">
        <a className="marketing-wordmark" href="/" aria-label="Causality home">
          <span>C</span> causality
        </a>
        <nav className="marketing-links" aria-label="Primary navigation">
          <a href="#product">Product</a>
          <a href="#workflow">How it works</a>
          <a href={githubUrl} target="_blank" rel="noreferrer">Open source</a>
          <a href="/docs">Docs</a>
        </nav>
        <div className="marketing-actions">
          <a className="marketing-sign-in" href="/app">Sign in</a>
          <a className="marketing-button marketing-button-dark" href="/app">Try the live demo <Arrow /></a>
        </div>
      </header>

      <main>
        <section className="marketing-hero">
          <div className="hero-status"><span /> Open source · OpenTelemetry native</div>
          <h1>Find the cause.<br />Not another chart.</h1>
          <p>Causality turns noisy production telemetry into ranked, evidence-backed explanations—so your team can move from alert to fix with confidence.</p>
          <div className="hero-actions">
            <a className="marketing-button marketing-button-dark" href="/app">Investigate the demo <Arrow /></a>
            <a className="marketing-button marketing-button-light" href={githubUrl} target="_blank" rel="noreferrer"><GitHub /> View on GitHub</a>
          </div>
          <p className="hero-footnote">No account required for the demo.</p>
        </section>

        <section className="product-stage" id="product" aria-label="Causality product preview">
          <div className="stage-grid" />
          <div className="product-window">
            <div className="window-bar">
              <div className="window-brand"><span>C</span> causality</div>
              <div className="window-context">Acme production <i /> live</div>
              <div className="window-avatar">NA</div>
            </div>
            <div className="window-body">
              <aside className="preview-sidebar">
                <button>+ New investigation</button>
                <div className="preview-label">Investigations <span>3</span></div>
                <div className="preview-incident active"><i /> Checkout latency spike<small>api, payments</small></div>
                <div className="preview-incident"><i /> Worker error rate<small>jobs, database</small></div>
                <div className="preview-incident"><i /> Intermittent 502s<small>gateway</small></div>
              </aside>
              <div className="preview-trace">
                <div className="preview-kicker">INVESTIGATION · OPEN</div>
                <h3>Checkout latency spike</h3>
                <p>12:41–12:56 UTC · 3 services · 1,284 spans</p>
                <div className="preview-metrics"><span><b>2.84s</b> p95 latency</span><span><b>18.3%</b> error rate</span><span><b>+241%</b> baseline</span></div>
                <div className="trace-heading"><span>Critical path</span><small>Duration</small></div>
                <TraceRow name="POST /checkout" service="api" width="91%" time="2.84s" error />
                <TraceRow name="authorize_payment" service="payments" width="78%" time="2.41s" error />
                <TraceRow name="SELECT customer" service="postgres" width="31%" time="842ms" />
                <TraceRow name="publish order" service="queue" width="11%" time="184ms" />
              </div>
              <aside className="preview-analysis">
                <div className="analysis-title"><span>Ranked causes</span><small>3 found</small></div>
                <div className="cause-card primary">
                  <div className="cause-rank"><span>01</span><b>92% confidence</b></div>
                  <h4>Connection pool saturation</h4>
                  <p>Payment requests waited on an exhausted Postgres pool after traffic increased.</p>
                  <div className="evidence-line"><i /> 4 linked spans</div>
                </div>
                <div className="cause-card">
                  <div className="cause-rank"><span>02</span><b>61% confidence</b></div>
                  <h4>Retry amplification</h4>
                </div>
              </aside>
            </div>
          </div>
        </section>

        <section className="workflow-section marketing-section" id="workflow">
          <div className="section-intro">
            <div className="marketing-kicker">The workflow</div>
            <h2>One incident.<br />Three deliberate moves.</h2>
            <p>Keep the investigation close to the telemetry. Causality assembles the signal, tests explanations, and links every conclusion back to evidence.</p>
          </div>
          <div className="workflow-list">
            <WorkflowStep number="01" title="Scope the moment" copy="Choose the affected environment, services, and time window. Start from an incident—not an empty query box." />
            <WorkflowStep number="02" title="Assemble the signal" copy="Correlate traces and logs across service boundaries while preserving the full path of the failure." />
            <WorkflowStep number="03" title="Rank the evidence" copy="Get competing causes ordered by confidence, with the exact spans and observations behind each one." />
          </div>
        </section>

        <section className="architecture-section marketing-section">
          <div className="architecture-copy">
            <div className="marketing-kicker">Built at the telemetry layer</div>
            <h2>Bring the signal you already have.</h2>
            <p>Causality speaks OpenTelemetry. Connect your existing collector, keep your instrumentation, and investigate across environments without another proprietary agent.</p>
            <a className="inline-link" href="/docs">Read the API documentation <Arrow /></a>
          </div>
          <div className="architecture-diagram" aria-label="Telemetry architecture diagram">
            <div className="diagram-inputs">
              <DiagramNode label="TRACES" detail="OTLP / HTTP" />
              <DiagramNode label="LOGS" detail="OTLP / HTTP" />
              <DiagramNode label="INCIDENT" detail="API / UI" />
            </div>
            <div className="diagram-lines"><span /><span /><span /></div>
            <div className="diagram-core"><div className="brand-mark">C</div><strong>CAUSALITY</strong><small>Evidence engine</small></div>
            <div className="diagram-arrow">→</div>
            <div className="diagram-output"><small>OUTPUT</small><strong>Ranked causes</strong><span>confidence · evidence · impact</span></div>
          </div>
        </section>

        <section className="principles-section marketing-section">
          <div className="marketing-kicker">Product principles</div>
          <h2>Built for the person holding the pager.</h2>
          <div className="principles-grid">
            <Principle mark="↗" title="Evidence, not vibes" copy="Every hypothesis is grounded in the spans and logs that support it." />
            <Principle mark="◎" title="OpenTelemetry native" copy="Use the instrumentation and collectors already running in your stack." />
            <Principle mark="◇" title="Open at the core" copy="Inspect it, self-host it, extend it, or run the managed version when you need scale." />
            <Principle mark="⌁" title="Designed for motion" copy="Stream analysis as it happens instead of waiting behind an opaque loading screen." />
          </div>
        </section>

        <section className="open-source-section marketing-section">
          <div>
            <div className="marketing-kicker">Open source</div>
            <h2>Infrastructure software should earn your trust.</h2>
          </div>
          <div className="open-source-copy">
            <p>The core of Causality is public. Read the code, understand how conclusions are produced, and run it inside your own environment.</p>
            <div className="repo-card">
              <div><GitHub /><span>janettai / <b>causality</b></span></div>
              <a href={githubUrl} target="_blank" rel="noreferrer">Browse repository <Arrow /></a>
            </div>
          </div>
        </section>

        <section className="final-cta">
          <div className="marketing-kicker">Start with a real incident</div>
          <h2>Turn telemetry into an answer.</h2>
          <p>Open the seeded investigation and see the complete path from trace to ranked cause.</p>
          <a className="marketing-button marketing-button-dark" href="/app">Try the live demo <Arrow /></a>
        </section>
      </main>

      <footer className="marketing-footer">
        <div className="marketing-wordmark"><span>C</span> causality</div>
        <p>Open-source incident intelligence for modern systems.</p>
        <div><a href={githubUrl}>GitHub</a><a href="/docs">Docs</a><a href="/app">Sign in</a></div>
        <small>© {new Date().getFullYear()} Janett AI</small>
      </footer>
    </div>
  );
}

function TraceRow({ name, service, width, time, error = false }: { name: string; service: string; width: string; time: string; error?: boolean }) {
  return <div className="trace-row"><div><strong>{name}</strong><small>{service}</small></div><div className="trace-track"><span className={error ? "error" : ""} style={{ width }} /></div><time>{time}</time></div>;
}

function WorkflowStep({ number, title, copy }: { number: string; title: string; copy: string }) {
  return <article className="workflow-step"><span>{number}</span><h3>{title}</h3><p>{copy}</p><div>→</div></article>;
}

function DiagramNode({ label, detail }: { label: string; detail: string }) {
  return <div><strong>{label}</strong><small>{detail}</small></div>;
}

function Principle({ mark, title, copy }: { mark: string; title: string; copy: string }) {
  return <article><span>{mark}</span><h3>{title}</h3><p>{copy}</p></article>;
}

function Arrow() { return <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 8h9M8.5 4.5 12 8l-3.5 3.5" /></svg>; }
function GitHub() { return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2.7a9.6 9.6 0 0 0-3 18.7c.5.1.7-.2.7-.5v-1.8c-2.8.6-3.4-1.2-3.4-1.2-.5-1.2-1.1-1.5-1.1-1.5-.9-.6.1-.6.1-.6 1 0 1.6 1 1.6 1 .9 1.6 2.4 1.1 2.9.9.1-.7.4-1.1.7-1.3-2.3-.3-4.7-1.1-4.7-5.1 0-1.1.4-2.1 1-2.8-.1-.3-.4-1.3.1-2.8 0 0 .9-.3 2.9 1.1a10 10 0 0 1 5.2 0c2-1.4 2.9-1.1 2.9-1.1.5 1.5.2 2.5.1 2.8.7.7 1 1.7 1 2.8 0 4-2.4 4.8-4.7 5.1.4.3.7 1 .7 1.9v2.8c0 .3.2.6.7.5A9.6 9.6 0 0 0 12 2.7Z" /></svg>; }
