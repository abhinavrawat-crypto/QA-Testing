import { useEffect, useState } from 'react'
import { Link, useSearchParams, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import api from '../services/api'

const FEATURES = [
  { id: 'score', label: 'Story Scoring', icon: '⭐', badge: 'Quality Audit', badgeClass: 'badge-blue', desc: 'Score and rewrite user stories with INVEST + Gherkin AC analysis.', href: '/feature-a' },
  { id: 'impact', label: 'Impact Analysis', icon: '🔍', badge: 'Vector Trace', badgeClass: 'badge-purple', desc: 'Trace test impact from JIRA story changes and generate Playwright scripts.', href: '/feature-b' },
  { id: 'discover', label: 'Story Discovery', icon: '🗺️', badge: 'Coverage Gap', badgeClass: 'badge-teal', desc: 'Find test cases without matching user stories and generate drafts.', href: '/feature-c' },
  { id: 'rootcause', label: 'Root Cause Analysis', icon: '🎯', badge: 'Defect Remediation', badgeClass: 'badge-red', desc: 'Trace a production bug back to a test gap, propose a fix, and verify across environments.', href: '/feature-d' },
]

export default function Dashboard() {
  const { user } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const activeFeature = searchParams.get('feature') || null

  const [jiraConns, setJiraConns] = useState([])
  const [githubConns, setGithubConns] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      api.get('/jira/connections').then(r => setJiraConns(r.data)),
      api.get('/github/connections').then(r => setGithubConns(r.data)),
    ]).finally(() => setLoading(false))
  }, [])

  const hasConnections = jiraConns.length > 0 || githubConns.length > 0

  if (loading) return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh' }}>
      <div className="spinner" style={{ width: 40, height: 40 }} />
    </div>
  )

  return (
    <div style={{ minHeight: 'calc(100vh - 64px)', padding: '3rem 0' }}>
      <div className="container" style={{ maxWidth: '1400px', margin: '0 auto', padding: '0 2rem' }}>
        {/* Header Hero Area */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1.5rem', marginBottom: '3rem' }}>
          <div>
            <h1 style={{ fontSize: '2.2rem', fontWeight: 800, letterSpacing: '-0.5px', marginBottom: '0.4rem', color: 'var(--text-primary)' }}>
              Welcome back, {user?.name?.split(' ')[0]} 👋
            </h1>
            <p style={{ color: 'var(--text-secondary)', fontSize: '1rem', margin: 0 }}>
              Launch automated quality workflows or manage your repository connections.
            </p>
          </div>

          {/* Quick Integration Status Pill Tags */}
          <div style={{ display: 'flex', gap: '0.75rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', padding: '0.5rem 1rem', borderRadius: 'var(--radius-full)', fontSize: '0.82rem' }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: jiraConns.length > 0 ? 'var(--color-emerald)' : 'var(--color-amber)' }} />
              <span style={{ color: 'var(--text-secondary)' }}>JIRA:</span>
              <strong style={{ color: 'var(--text-primary)' }}>{jiraConns.length > 0 ? `${jiraConns.length} Connected` : 'Disconnected'}</strong>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', padding: '0.5rem 1rem', borderRadius: 'var(--radius-full)', fontSize: '0.82rem' }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: githubConns.length > 0 ? 'var(--color-emerald)' : 'var(--color-amber)' }} />
              <span style={{ color: 'var(--text-secondary)' }}>GitHub:</span>
              <strong style={{ color: 'var(--text-primary)' }}>{githubConns.length > 0 ? `${githubConns.length} Connected` : 'Disconnected'}</strong>
            </div>
          </div>
        </div>

        {/* Missing Connections Alert */}
        {!hasConnections && (
          <div className="alert alert-info" style={{ marginBottom: '2.5rem', borderLeft: '4px solid var(--color-teal)' }}>
            🔗 <strong>No connections configured.</strong> Please <Link to="/onboarding" style={{ color: 'var(--color-teal)', textDecoration: 'underline' }}>Connect JIRA and GitHub</Link> to enable full impact tracing and Playwright generation.
          </div>
        )}

        {/* Workflows Section */}
        <div style={{ marginBottom: '4rem' }}>
          <h2 style={{ fontSize: '1.1rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '1px', fontWeight: 700, marginBottom: '1.5rem' }}>
            Choose a Workflow
          </h2>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: '2rem' }}>
            {FEATURES.map(f => {
              // Custom colors & tags for each card
              const isScore = f.id === 'score';
              const isImpact = f.id === 'impact';
              const isDiscover = f.id === 'discover';
              const borderTheme = isScore ? 'rgba(37,99,235,0.4)' : isImpact ? 'rgba(139,92,246,0.4)' : isDiscover ? 'rgba(45,212,191,0.4)' : 'rgba(225,29,72,0.4)';
              const badgeTheme = isScore ? 'badge-blue' : isImpact ? 'badge-purple' : isDiscover ? 'badge-green' : 'badge-red';

              return (
                <div
                  key={f.id}
                  onClick={() => navigate(f.href)}
                  className="glass"
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    padding: '2rem',
                    borderRadius: 'var(--radius-lg)',
                    border: '1px solid var(--color-border)',
                    cursor: 'pointer',
                    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                    position: 'relative',
                    overflow: 'hidden',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.transform = 'translateY(-4px)';
                    e.currentTarget.style.borderColor = borderTheme;
                    e.currentTarget.style.boxShadow = '0 12px 24px -10px rgba(0, 0, 0, 0.4)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.transform = 'none';
                    e.currentTarget.style.borderColor = 'var(--color-border)';
                    e.currentTarget.style.boxShadow = 'none';
                  }}
                >
                  {/* Top Badge Row */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
                    <span className={`badge ${badgeTheme}`} style={{ fontSize: '0.72rem', padding: '0.25rem 0.6rem', fontWeight: 700 }}>
                      {f.badge}
                    </span>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      {isScore ? 'JIRA Only' : 'JIRA + GitHub'}
                    </span>
                  </div>

                  {/* Body Content */}
                  <div style={{ flex: 1 }}>
                    <h3 style={{ fontSize: '1.3rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '0.6rem' }}>
                      {f.label}
                    </h3>
                    <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', lineHeight: 1.5, margin: 0 }}>
                      {f.desc}
                    </p>
                  </div>

                  {/* Footer launch action */}
                  <div style={{ marginTop: '2rem', borderTop: '1px solid var(--color-border)', paddingTop: '1rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Prerequisites met</span>
                    <span style={{ color: 'var(--color-teal)', fontWeight: 600, fontSize: '0.9rem', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                      Launch Workflow <span style={{ transition: 'transform 0.2s' }}>→</span>
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Integration Hub Section */}
        <div style={{ borderTop: '1px solid var(--color-border)', paddingTop: '3rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
            <h2 style={{ fontSize: '1.1rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '1px', fontWeight: 700, margin: 0 }}>
              Integration Hub
            </h2>
            <Link to="/onboarding" className="btn btn-secondary" style={{ fontSize: '0.8rem', padding: '0.45rem 1rem' }}>
              + Add Connection
            </Link>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(480px, 1fr))', gap: '2rem' }}>
            {/* JIRA Column */}
            <div className="glass" style={{ padding: '1.5rem', borderRadius: 'var(--radius-lg)' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem', borderBottom: '1px solid var(--color-border)', paddingBottom: '0.75rem' }}>
                <span style={{ fontWeight: 700, fontSize: '0.95rem', color: 'var(--text-primary)' }}>JIRA Integration Sites</span>
                <span className="badge badge-blue">{jiraConns.length} Active</span>
              </div>
              {jiraConns.length === 0 ? (
                <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', margin: '1rem 0' }}>No JIRA sites configured yet.</p>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  {jiraConns.map(c => (
                    <div key={c.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: 'var(--color-surface-2)', padding: '0.75rem 1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--color-border)' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flex: 1, overflow: 'hidden' }}>
                        <span style={{ width: 10, height: 10, borderRadius: '50%', background: 'var(--color-emerald)', flexShrink: 0 }} />
                        <span style={{ fontSize: '0.88rem', fontWeight: 600, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {c.site_name}
                        </span>
                      </div>
                      <span className="badge badge-blue" style={{ fontSize: '0.7rem' }}>{c.auth_type}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* GitHub Column */}
            <div className="glass" style={{ padding: '1.5rem', borderRadius: 'var(--radius-lg)' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem', borderBottom: '1px solid var(--color-border)', paddingBottom: '0.75rem' }}>
                <span style={{ fontWeight: 700, fontSize: '0.95rem', color: 'var(--text-primary)' }}>GitHub Integration Accounts</span>
                <span className="badge badge-purple">{githubConns.length} Active</span>
              </div>
              {githubConns.length === 0 ? (
                <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', margin: '1rem 0' }}>No GitHub profiles configured yet.</p>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  {githubConns.map(c => (
                    <div key={c.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: 'var(--color-surface-2)', padding: '0.75rem 1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--color-border)' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flex: 1, overflow: 'hidden' }}>
                        <span style={{ width: 10, height: 10, borderRadius: '50%', background: 'var(--color-emerald)', flexShrink: 0 }} />
                        <span style={{ fontSize: '0.88rem', fontWeight: 600, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {c.connection_name}
                        </span>
                      </div>
                      <span className="badge badge-purple" style={{ fontSize: '0.7rem' }}>{c.auth_type}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
