import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../services/api'

const STEPS = ['Welcome', 'JIRA', 'GitHub', 'Done']

export default function Onboarding() {
  const navigate = useNavigate()
  const [step, setStep] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState('')
  const [success, setSuccess] = useState('')

  // JIRA form
  const [jiraForm, setJiraForm] = useState({ site_url:'', site_name:'', auth_type:'pat', token:'', email:'' })
  // GitHub form
  const [ghForm, setGhForm] = useState({ api_base_url:'https://api.github.com', connection_name:'github.com', auth_type:'pat', token:'' })

  const next = () => { setError(''); setSuccess(''); setStep(s => s + 1) }
  const skip = () => { setError(''); setSuccess(''); setStep(s => s + 1) }

  const connectJira = async (e) => {
    e.preventDefault(); setError(''); setLoading(true)
    try {
      await api.post('/jira/connections', jiraForm)
      setSuccess('JIRA connected successfully!')
      setTimeout(next, 800)
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to connect JIRA')
    } finally { setLoading(false) }
  }

  const connectGitHub = async (e) => {
    e.preventDefault(); setError(''); setLoading(true)
    try {
      await api.post('/github/connections', ghForm)
      setSuccess('GitHub connected successfully!')
      setTimeout(next, 800)
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to connect GitHub')
    } finally { setLoading(false) }
  }

  return (
    <div style={{ minHeight:'calc(100vh - 64px)', display:'flex', alignItems:'center', justifyContent:'center', padding:'2rem' }}>
      <div style={{ width:'100%', maxWidth:540 }}>
        {/* Step dots */}
        <div style={{ display:'flex', justifyContent:'center', gap:'0.5rem', marginBottom:'2rem' }}>
          {STEPS.map((_, i) => (
            <div key={i} className={`step-dot ${i === step ? 'active' : i < step ? 'done' : ''}`} />
          ))}
        </div>

        <div className="glass animate-fade-up" style={{ padding:'2.5rem' }}>
          {error   && <div className="alert alert-error"   style={{ marginBottom:'1rem' }}>⚠ {error}</div>}
          {success && <div className="alert alert-success" style={{ marginBottom:'1rem' }}>✓ {success}</div>}

          {/* Step 0 — Welcome */}
          {step === 0 && (
            <div style={{ textAlign:'center' }}>
              <div style={{ fontSize:'3rem', marginBottom:'1rem' }}>👋</div>
              <h2 style={{ marginBottom:'0.75rem' }}>Welcome aboard!</h2>
              <p style={{ marginBottom:'2rem', lineHeight:1.75 }}>
                Let's connect your <strong style={{ color:'var(--text-primary)' }}>JIRA</strong> and <strong style={{ color:'var(--text-primary)' }}>GitHub</strong> accounts so the platform can access your stories and test repositories.
                <br /><br />
                You can connect multiple JIRA sites and GitHub organizations — and add more any time from settings.
              </p>
              <div style={{ display:'flex', gap:'0.75rem', justifyContent:'center' }}>
                <button className="btn btn-primary" onClick={next} style={{ padding:'0.8rem 2rem' }}>Let's connect →</button>
              </div>
            </div>
          )}

          {/* Step 1 — JIRA */}
          {step === 1 && (
            <>
              <div style={{ marginBottom:'1.5rem' }}>
                <span className="badge badge-blue" style={{ marginBottom:'0.5rem' }}>Step 2 of 3</span>
                <h2 style={{ marginBottom:'0.4rem' }}>Connect JIRA</h2>
                <p style={{ fontSize:'0.875rem' }}>Supports JIRA Cloud OAuth 2.0 and Personal Access Tokens (PAT/API Token).</p>
              </div>
              <form onSubmit={connectJira} style={{ display:'flex', flexDirection:'column', gap:'1rem' }}>
                <div className="input-group">
                  <label className="input-label">JIRA Site URL</label>
                  <input className="input" placeholder="https://yourcompany.atlassian.net" value={jiraForm.site_url}
                    onChange={e => setJiraForm(f => ({...f, site_url: e.target.value}))} required />
                </div>
                <div className="input-group">
                  <label className="input-label">Site display name</label>
                  <input className="input" placeholder="My Company JIRA" value={jiraForm.site_name}
                    onChange={e => setJiraForm(f => ({...f, site_name: e.target.value}))} required />
                </div>
                <div className="input-group">
                  <label className="input-label">Auth method</label>
                  <select className="input" value={jiraForm.auth_type} onChange={e => setJiraForm(f => ({...f, auth_type: e.target.value}))}>
                    <option value="pat">Personal Access Token (PAT / API Token)</option>
                    <option value="oauth">OAuth 2.0</option>
                  </select>
                </div>
                {jiraForm.auth_type === 'pat' && (
                  <div className="input-group">
                    <label className="input-label">Account email (for PAT)</label>
                    <input className="input" type="email" placeholder="you@company.com" value={jiraForm.email}
                      onChange={e => setJiraForm(f => ({...f, email: e.target.value}))} required />
                  </div>
                )}
                <div className="input-group">
                  <label className="input-label">API Token / PAT</label>
                  <input className="input" type="password" placeholder="Paste token here" value={jiraForm.token}
                    onChange={e => setJiraForm(f => ({...f, token: e.target.value}))} required />
                  <span style={{ fontSize:'0.75rem', color:'var(--text-muted)' }}>Encrypted at rest with AES-256. Never stored in plain text.</span>
                </div>
                <div style={{ display:'flex', gap:'0.75rem', marginTop:'0.25rem' }}>
                  <button type="submit" className="btn btn-primary" disabled={loading} style={{ flex:1, justifyContent:'center' }}>
                    {loading ? <><span className="spinner" style={{ width:16, height:16 }} /> Connecting…</> : 'Connect JIRA →'}
                  </button>
                  <button type="button" className="btn btn-secondary" onClick={skip}>Skip for now</button>
                </div>
              </form>
            </>
          )}

          {/* Step 2 — GitHub */}
          {step === 2 && (
            <>
              <div style={{ marginBottom:'1.5rem' }}>
                <span className="badge badge-purple" style={{ marginBottom:'0.5rem' }}>Step 3 of 3</span>
                <h2 style={{ marginBottom:'0.4rem' }}>Connect GitHub</h2>
                <p style={{ fontSize:'0.875rem' }}>Supports github.com and GitHub Enterprise Server (GHES).</p>
              </div>
              <form onSubmit={connectGitHub} style={{ display:'flex', flexDirection:'column', gap:'1rem' }}>
                <div className="input-group">
                  <label className="input-label">GitHub API Base URL</label>
                  <input className="input" placeholder="https://api.github.com" value={ghForm.api_base_url}
                    onChange={e => setGhForm(f => ({...f, api_base_url: e.target.value}))} required />
                  <span style={{ fontSize:'0.75rem', color:'var(--text-muted)' }}>For GHES: https://your-ghes-host/api/v3</span>
                </div>
                <div className="input-group">
                  <label className="input-label">Connection name</label>
                  <input className="input" placeholder="github.com" value={ghForm.connection_name}
                    onChange={e => setGhForm(f => ({...f, connection_name: e.target.value}))} required />
                </div>
                <div className="input-group">
                  <label className="input-label">Personal Access Token (PAT)</label>
                  <input className="input" type="password" placeholder="ghp_... or GitHub token" value={ghForm.token}
                    onChange={e => setGhForm(f => ({...f, token: e.target.value}))} required />
                  <span style={{ fontSize:'0.75rem', color:'var(--text-muted)' }}>Needs: repo, read:org, workflow scopes. Encrypted at rest.</span>
                </div>
                <div style={{ display:'flex', gap:'0.75rem', marginTop:'0.25rem' }}>
                  <button type="submit" className="btn btn-primary" disabled={loading} style={{ flex:1, justifyContent:'center' }}>
                    {loading ? <><span className="spinner" style={{ width:16, height:16 }} /> Connecting…</> : 'Connect GitHub →'}
                  </button>
                  <button type="button" className="btn btn-secondary" onClick={skip}>Skip for now</button>
                </div>
              </form>
            </>
          )}

          {/* Step 3 — Done */}
          {step === 3 && (
            <div style={{ textAlign:'center' }}>
              <div style={{ fontSize:'3.5rem', marginBottom:'1rem' }}>🎉</div>
              <h2 style={{ marginBottom:'0.75rem' }}>You're all set!</h2>
              <p style={{ marginBottom:'2rem', lineHeight:1.75 }}>
                Your connections are saved. Head to the dashboard to start scoring stories, running impact analysis, or discovering missing coverage.
              </p>
              <button className="btn btn-primary" onClick={() => navigate('/dashboard')} style={{ padding:'0.8rem 2rem' }}>
                Go to Dashboard →
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
