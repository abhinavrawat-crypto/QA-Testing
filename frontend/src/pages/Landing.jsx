import { useState } from 'react'
import { Link as RouterLink } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

const WORKFLOW_CARDS = [
  {
    id: 'score',
    tag: 'Requirements Auditing',
    title: 'INVEST Story Auditing & AI Rewriting',
    description: 'Instantly score JIRA backlog items against INVEST criteria and Gherkin completeness. Review AI-proposed story rewrites with side-by-side visual diffs and approved JIRA sync.',
    href: '/feature-a',
    accentColor: '#2563eb',
    icon: '⭐',
    badgeText: 'INVEST Compliant',
    bullets: ['INVEST Quality Scoring Algorithm', 'Gherkin Acceptance Criteria Check', 'Side-by-Side Visual Diff Canvas', 'Direct JIRA Backlog Write-Back'],
  },
  {
    id: 'impact',
    tag: 'Impact Analysis & Code Gen',
    title: 'Semantic Test Impact & PR Automation',
    description: 'Index .feature and Playwright specs into pgvector embeddings. Instantly identify impacted tests when JIRA requirements change, generate Playwright specs, and open GitHub PRs.',
    href: '/feature-b',
    accentColor: '#7c3aed',
    icon: '🔍',
    badgeText: 'Vector Search Engine',
    bullets: ['pgvector Cosine Search', 'Candidate Impact Ranking', 'Automated Playwright Code Gen', 'GitHub Branch & PR Creation'],
  },
  {
    id: 'discovery',
    tag: 'Coverage Discovery',
    title: 'Unmatched Test-to-Story Reverse Mapping',
    description: 'Scan your test suites to discover test cases lacking business requirements. Auto-draft INVEST-compliant JIRA stories and publish them directly to your backlog with one click.',
    href: '/feature-c',
    accentColor: '#0d9488',
    icon: '🗺️',
    badgeText: 'Reverse Index Engine',
    bullets: ['Test-to-Story Reverse Index', 'AI Draft Story Generation', 'Inline Spec & Summary Editor', 'One-Click JIRA Issue Push'],
  },
]

const TRUST_METRICS = [
  { value: '0', label: 'Silent Writes Ever', detail: 'Strict Human-in-the-Loop Governance' },
  { value: '< 50ms', label: 'pgvector Search Latency', detail: 'Real-time Vector Embedding Index' },
  { value: '100%', label: 'AES-256 Encrypted', detail: 'Enterprise Secret Isolation' },
  { value: 'SOC-2', label: 'Compliance Architecture', detail: 'Complete Audit Trail & Access Logs' },
]

export default function Landing() {
  const { user } = useAuth()
  const [activeTab, setActiveTab] = useState('impact')

  return (
    <div style={{ minHeight: 'calc(100vh - 64px)', background: '#ffffff', color: '#0f172a' }}>
      {/* Hero Section */}
      <section style={{ padding: '5.5rem 0 4rem', textAlign: 'center', position: 'relative', overflow: 'hidden', background: 'linear-gradient(180deg, #f8fafc 0%, #ffffff 100%)' }}>
        {/* Soft background glow blobs */}
        <div className="animate-float" style={{ position: 'absolute', top: '-10%', left: '25%', width: 650, height: 650, borderRadius: '50%', background: 'radial-gradient(circle, rgba(37, 99, 235, 0.08) 0%, transparent 70%)', pointerEvents: 'none' }} />
        <div className="animate-float" style={{ position: 'absolute', top: '15%', right: '20%', width: 500, height: 500, borderRadius: '50%', background: 'radial-gradient(circle, rgba(13, 148, 136, 0.06) 0%, transparent 70%)', animationDelay: '3s', pointerEvents: 'none' }} />

        <div className="container" style={{ position: 'relative', zIndex: 1 }}>
          <div className="animate-fade-up" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.6rem', padding: '0.4rem 1.1rem', borderRadius: '100px', background: 'rgba(37, 99, 235, 0.06)', border: '1px solid rgba(37, 99, 235, 0.2)', marginBottom: '1.75rem' }}>
            <span className="animate-pulse-glow" style={{ width: 8, height: 8, borderRadius: '50%', background: '#2563eb' }} />
            <span style={{ fontSize: '0.78rem', fontWeight: 700, color: '#1d4ed8', letterSpacing: '1px', textTransform: 'uppercase' }}>
              QualityAI Enterprise — Requirements & Test Impact Intelligence
            </span>
          </div>

          <h1 className="animate-fade-up-delay-1" style={{ fontSize: 'clamp(2.5rem, 5.2vw, 4.2rem)', fontWeight: 800, letterSpacing: '-1.5px', lineHeight: 1.1, marginBottom: '1.5rem', color: '#0f172a' }}>
            Precision Quality Intelligence<br />
            <span className="animate-shimmer">
              for Modern Engineering Teams
            </span>
          </h1>

          <p className="animate-fade-up-delay-2" style={{ maxWidth: 720, margin: '0 auto 2.5rem', fontSize: '1.15rem', color: '#475569', lineHeight: 1.75, fontWeight: 400 }}>
            Unify JIRA user stories and Playwright automated test suites. Powered by Google Gemini vector embeddings, strict INVEST quality auditing, and 100% human-governed pull request automation.
          </p>

          <div className="animate-fade-up-delay-3" style={{ display: 'flex', gap: '1.25rem', justifyContent: 'center', flexWrap: 'wrap' }}>
            {user ? (
              <RouterLink to="/dashboard" className="btn btn-primary" style={{ padding: '0.9rem 2.25rem', fontSize: '1rem', background: '#2563eb', color: '#fff', fontWeight: 700, borderRadius: 10 }}>
                Enter QualityAI Console →
              </RouterLink>
            ) : (
              <>
                <RouterLink to="/register" className="btn btn-primary" style={{ padding: '0.9rem 2.25rem', fontSize: '1rem', background: '#2563eb', color: '#fff', fontWeight: 700, borderRadius: 10 }}>
                  Launch QualityAI Console →
                </RouterLink>
                <RouterLink to="/login" className="btn btn-secondary" style={{ padding: '0.9rem 2.25rem', fontSize: '1rem', borderRadius: 10 }}>
                  Sign In
                </RouterLink>
              </>
            )}
          </div>
        </div>
      </section>

      {/* Trust Metrics Bar */}
      <section style={{ padding: '2.25rem 0', borderTop: '1px solid #e2e8f0', borderBottom: '1px solid #e2e8f0', background: '#f8fafc' }}>
        <div className="container">
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '2rem', textAlign: 'center' }}>
            {TRUST_METRICS.map(m => (
              <div key={m.label} className="hover-lift" style={{ padding: '0.5rem', borderRadius: 8 }}>
                <div style={{ fontSize: '2.2rem', fontWeight: 800, color: '#0f172a', letterSpacing: '-0.5px' }}>{m.value}</div>
                <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#2563eb', marginTop: '0.2rem' }}>{m.label}</div>
                <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '0.1rem' }}>{m.detail}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Enterprise Interactive Workspace Preview */}
      <section style={{ padding: '5rem 0', background: '#ffffff' }}>
        <div className="container">
          <div style={{ textAlign: 'center', marginBottom: '3rem' }}>
            <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#2563eb', letterSpacing: '1px', textTransform: 'uppercase', background: 'rgba(37, 99, 235, 0.08)', padding: '0.35rem 0.85rem', borderRadius: 100, border: '1px solid rgba(37, 99, 235, 0.2)' }}>
              Interactive Console Preview
            </span>
            <h2 style={{ fontSize: '2rem', fontWeight: 800, color: '#0f172a', marginTop: '0.75rem', marginBottom: '0.5rem' }}>
              Integrated Requirements & Test Lifecycle
            </h2>
            <p style={{ maxWidth: 620, margin: '0 auto', fontSize: '0.95rem', color: '#475569' }}>
              Eliminate coverage gaps, outdated tests, and ambiguous backlog items with automated AI governance.
            </p>
          </div>

          {/* Interactive Console Window with Glass Hover Effect */}
          <div className="hover-lift" style={{ background: '#0f172a', borderRadius: 16, border: '1px solid #1e293b', boxShadow: '0 20px 40px rgba(15, 23, 42, 0.15)', overflow: 'hidden' }}>
            {/* Top Bar Tabs */}
            <div style={{ display: 'flex', background: '#1e293b', borderBottom: '1px solid #334155', padding: '0 1rem' }}>
              <button
                onClick={() => setActiveTab('score')}
                style={{
                  padding: '1rem 1.5rem',
                  background: 'none',
                  border: 'none',
                  borderBottom: activeTab === 'score' ? '3px solid #60a5fa' : '3px solid transparent',
                  color: activeTab === 'score' ? '#ffffff' : '#94a3b8',
                  fontWeight: activeTab === 'score' ? 700 : 500,
                  fontSize: '0.88rem',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                }}
              >
                ⭐ INVEST Story Audit
              </button>
              <button
                onClick={() => setActiveTab('impact')}
                style={{
                  padding: '1rem 1.5rem',
                  background: 'none',
                  border: 'none',
                  borderBottom: activeTab === 'impact' ? '3px solid #60a5fa' : '3px solid transparent',
                  color: activeTab === 'impact' ? '#ffffff' : '#94a3b8',
                  fontWeight: activeTab === 'impact' ? 700 : 500,
                  fontSize: '0.88rem',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                }}
              >
                🔍 Vector Test Impact Analysis
              </button>
              <button
                onClick={() => setActiveTab('discovery')}
                style={{
                  padding: '1rem 1.5rem',
                  background: 'none',
                  border: 'none',
                  borderBottom: activeTab === 'discovery' ? '3px solid #60a5fa' : '3px solid transparent',
                  color: activeTab === 'discovery' ? '#ffffff' : '#94a3b8',
                  fontWeight: activeTab === 'discovery' ? 700 : 500,
                  fontSize: '0.88rem',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                }}
              >
                🗺️ Unmatched Story Discovery
              </button>
            </div>

            {/* Console Body */}
            <div style={{ padding: '1.75rem', background: '#090d16', fontFamily: 'JetBrains Mono, monospace', fontSize: '0.85rem' }}>
              {activeTab === 'score' && (
                <div className="animate-fade-up">
                  <div style={{ display: 'flex', justifyContent: 'space-between', color: '#64748b', marginBottom: '1rem', paddingBottom: '0.75rem', borderBottom: '1px solid #1e293b' }}>
                    <span>JIRA Issue: PAY-1042 — "Implement Stripe 3D Secure Verification"</span>
                    <span style={{ color: '#10b981', fontWeight: 700 }}>INVEST Score: 92/100 (Grade A)</span>
                  </div>
                  <pre style={{ color: '#e2e8f0', margin: 0, whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>
{`[INVEST AUDIT SUMMARY]
✓ Independent: Story has no blocking external dependencies.
✓ Negotiable: Focuses on business outcome rather than implementation detail.
✓ Valuable: Direct user value defined for 3DS authentication flow.
✓ Estimable: Clear scope for 3-point story estimation.
✓ Small: Fits within single 2-week sprint iteration.
✓ Testable: 4 Gherkin Given/When/Then scenarios generated.

[PROPOSED JIRA SYNC]
Approved rewrite ready to write back directly to JIRA issue PAY-1042.`}
                  </pre>
                </div>
              )}

              {activeTab === 'impact' && (
                <div className="animate-fade-up">
                  <div style={{ display: 'flex', justifyContent: 'space-between', color: '#64748b', marginBottom: '1rem', paddingBottom: '0.75rem', borderBottom: '1px solid #1e293b' }}>
                    <span>Vector Engine: pgvector Cosine Distance Query</span>
                    <span style={{ color: '#60a5fa', fontWeight: 700 }}>3 Candidate Tests Ranked</span>
                  </div>
                  <pre style={{ color: '#e2e8f0', margin: 0, whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>
{`[SEMANTIC IMPACT MATRIX]
1. tests/payment/checkout.spec.ts   │ Similarity: 0.94 │ Action: Update test assertion
2. tests/auth/mfa.spec.ts           │ Similarity: 0.31 │ Action: Unaffected
3. tests/billing/invoices.spec.ts   │ Similarity: 0.12 │ Action: Unaffected

[PLAYWRIGHT SCRIPT GENERATOR]
Created Playwright spec -> tests/payment/checkout.spec.ts
GitHub Pull Request -> branch: qualityai/test-update/pay-1042 (#148)`}
                  </pre>
                </div>
              )}

              {activeTab === 'discovery' && (
                <div className="animate-fade-up">
                  <div style={{ display: 'flex', justifyContent: 'space-between', color: '#64748b', marginBottom: '1rem', paddingBottom: '0.75rem', borderBottom: '1px solid #1e293b' }}>
                    <span>Reverse Index Scan: repo 'fintech-core'</span>
                    <span style={{ color: '#f59e0b', fontWeight: 700 }}>1 Unmatched Test Case Found</span>
                  </div>
                  <pre style={{ color: '#e2e8f0', margin: 0, whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>
{`[UNMATCHED TEST REVERSE INDEX]
Test File: tests/subscriptions/cancel_flow.spec.ts
Nearest JIRA Story Distance: 0.41 (Below 0.50 Threshold)

AI Drafted JIRA Story:
Summary: As a subscriber, I want to cancel my auto-renewing plan in 2 clicks.
Gherkin Scenario:
  Given an active paying subscriber
  When they click "Cancel Subscription" and confirm prompt
  Then their subscription status transitions to "pending_cancellation"`}
                  </pre>
                </div>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* Workflows Cards Section with Hover Lift */}
      <section style={{ padding: '5rem 0 6rem', background: '#f8fafc', borderTop: '1px solid #e2e8f0' }}>
        <div className="container">
          <div style={{ textAlign: 'center', marginBottom: '3.5rem' }}>
            <h2 style={{ fontSize: '2rem', fontWeight: 800, color: '#0f172a', marginBottom: '0.5rem' }}>
              Enterprise Quality Workflows
            </h2>
            <p style={{ maxWidth: 580, margin: '0 auto', fontSize: '0.95rem', color: '#475569' }}>
              Select a workflow to launch into the QualityAI execution environment.
            </p>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: '2rem' }}>
            {WORKFLOW_CARDS.map(w => (
              <div
                key={w.id}
                className="hover-lift"
                style={{
                  background: '#ffffff',
                  borderRadius: 16,
                  padding: '2.25rem',
                  border: '1px solid #e2e8f0',
                  display: 'flex',
                  flexDirection: 'column',
                  justify: 'space-between',
                  borderTop: `4px solid ${w.accentColor}`,
                }}
              >
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
                    <span style={{ fontSize: '0.78rem', fontWeight: 700, color: w.accentColor, letterSpacing: '0.5px', textTransform: 'uppercase' }}>{w.tag}</span>
                    <span style={{ fontSize: '1.5rem' }}>{w.icon}</span>
                  </div>
                  <h3 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#0f172a', marginBottom: '0.75rem' }}>{w.title}</h3>
                  <p style={{ fontSize: '0.88rem', color: '#475569', lineHeight: 1.65, marginBottom: '1.5rem' }}>{w.description}</p>

                  <div style={{ marginBottom: '1.75rem', display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                    {w.bullets.map(b => (
                      <div key={b} style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', fontSize: '0.82rem', color: '#334155' }}>
                        <span style={{ color: w.accentColor, fontWeight: 900 }}>✓</span>
                        {b}
                      </div>
                    ))}
                  </div>
                </div>

                <div>
                  <RouterLink
                    to={user ? w.href : '/register'}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justify: 'center',
                      gap: '0.5rem',
                      width: '100%',
                      padding: '0.8rem 1.25rem',
                      background: '#f8fafc',
                      border: '1px solid #cbd5e1',
                      borderRadius: 10,
                      color: '#0f172a',
                      fontWeight: 600,
                      fontSize: '0.9rem',
                      textDecoration: 'none',
                      transition: 'all 0.2s ease',
                    }}
                  >
                    Launch Workflow →
                  </RouterLink>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Enterprise Security Callout */}
      <section style={{ padding: '4rem 0', background: '#ffffff', borderTop: '1px solid #e2e8f0' }}>
        <div className="container" style={{ maxWidth: 900, margin: '0 auto', textAlign: 'center' }}>
          <h3 style={{ fontSize: '1.5rem', fontWeight: 800, color: '#0f172a', marginBottom: '0.75rem' }}>
            Enterprise Governance & Security Built-In
          </h3>
          <p style={{ fontSize: '0.92rem', color: '#475569', lineHeight: 1.7, marginBottom: '2rem' }}>
            Every AI suggestion requires explicit human approval. No silent write-backs to JIRA or GitHub. Integration credentials are encrypted at rest using AES-256.
          </p>
          <RouterLink
            to={user ? '/dashboard' : '/register'}
            className="btn btn-primary"
            style={{ padding: '0.9rem 2.25rem', background: '#2563eb', color: '#fff', fontWeight: 700, borderRadius: 10 }}
          >
            {user ? 'Open QualityAI Console' : 'Get Started Free'}
          </RouterLink>
        </div>
      </section>
    </div>
  )
}
