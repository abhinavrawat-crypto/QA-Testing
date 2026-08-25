import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../services/api'

const AVAILABLE_MODELS = [
  { id: 'gemini-3.5-flash', label: 'Gemini 3.5 Flash (Recommended — High Quota & Fast)', group: 'Latest 3.x' },
  { id: 'gemini-3.1-pro-preview', label: 'Gemini 3.1 Pro (Pro Reasoning — Requires Paid Tier)', group: 'Latest 3.x' },
  { id: 'gemini-3.1-flash-lite', label: 'Gemini 3.1 Flash Lite (Ultra-fast lightweight)', group: 'Latest 3.x' },
  { id: 'gemini-2.5-pro', label: 'Gemini 2.5 Pro (Advanced Reasoning)', group: '2.x Series' },
  { id: 'gemini-2.5-flash', label: 'Gemini 2.5 Flash (Fast)', group: '2.x Series' },
]

export default function Settings() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [showKey, setShowKey] = useState(false)

  const [settingsStatus, setSettingsStatus] = useState({
    gemini_api_key_configured: false,
    gemini_api_key_masked: '',
    gemini_model: 'gemini-3.5-flash',
  })

  const [apiKeyInput, setApiKeyInput] = useState('')
  const [selectedModel, setSelectedModel] = useState('gemini-3.5-flash')
  const [jiraConns, setJiraConns] = useState([])
  const [ghConns, setGhConns] = useState([])

  const loadSettings = async () => {
    setLoading(true)
    setError('')
    try {
      const [resSettings, resJira, resGh] = await Promise.allSettled([
        api.get('/settings'),
        api.get('/jira/connections'),
        api.get('/github/connections'),
      ])

      if (resSettings.status === 'fulfilled') {
        setSettingsStatus(resSettings.value.data)
        if (resSettings.value.data.gemini_model) {
          setSelectedModel(resSettings.value.data.gemini_model)
        }
      }
      if (resJira.status === 'fulfilled') {
        setJiraConns(resJira.value.data || [])
      }
      if (resGh.status === 'fulfilled') {
        setGhConns(resGh.value.data || [])
      }
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to load settings')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadSettings()
  }, [])

  const handleSaveGeminiSettings = async (e) => {
    e.preventDefault()
    setSaving(true)
    setError('')
    setSuccess('')
    try {
      const payload = {
        gemini_model: selectedModel,
      }
      if (apiKeyInput.trim()) {
        payload.gemini_api_key = apiKeyInput.trim()
      }
      const res = await api.post('/settings', payload)
      setSettingsStatus(res.data)
      setApiKeyInput('')
      setSuccess('Gemini AI settings updated and saved successfully!')
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to update Gemini AI settings')
    } finally {
      setSaving(false)
    }
  }

  const handleRemoveJiraConnection = async (id) => {
    if (!window.confirm('Are you sure you want to remove this JIRA connection?')) return
    setError('')
    setSuccess('')
    try {
      await api.delete(`/jira/connections/${id}`)
      setSuccess('JIRA connection removed successfully.')
      loadSettings()
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to remove JIRA connection')
    }
  }

  const handleRemoveGithubConnection = async (id) => {
    if (!window.confirm('Are you sure you want to remove this GitHub connection?')) return
    setError('')
    setSuccess('')
    try {
      await api.delete(`/github/connections/${id}`)
      setSuccess('GitHub connection removed successfully.')
      loadSettings()
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to remove GitHub connection')
    }
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh' }}>
        <div className="spinner" style={{ width: 40, height: 40 }} />
      </div>
    )
  }

  return (
    <div style={{ padding: '2rem', maxWidth: '1400px', margin: '0 auto' }}>
      <div style={{ marginBottom: '2rem' }}>
        <span className="badge badge-purple" style={{ marginBottom: '0.5rem' }}>Platform Settings</span>
        <h2 style={{ marginBottom: '0.4rem' }}>System Settings & Integrations</h2>
        <p style={{ fontSize: '0.9rem' }}>
          Configure your Google Gemini AI key, model preferences, JIRA cloud credentials, and GitHub repositories.
        </p>
      </div>

      {error && <div className="alert alert-error" style={{ marginBottom: '1.5rem' }}>⚠ {error}</div>}
      {success && <div className="alert alert-success" style={{ marginBottom: '1.5rem' }}>✓ {success}</div>}

      {/* Section 1: Google Gemini AI Key & Model */}
      <div className="glass" style={{ padding: '1.75rem', marginBottom: '1.75rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <div style={{ fontSize: '1.5rem' }}>🤖</div>
            <div>
              <h3 style={{ fontSize: '1.05rem', margin: 0 }}>Google Gemini AI Provider</h3>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                Active Model: <strong style={{ color: 'var(--text-primary)' }}>{settingsStatus.gemini_model}</strong>
              </span>
            </div>
          </div>
          <div>
            {settingsStatus.gemini_api_key_configured ? (
              <span className="badge badge-green" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
                ✓ Connected {settingsStatus.gemini_api_key_masked ? `(${settingsStatus.gemini_api_key_masked})` : ''}
              </span>
            ) : (
              <span className="badge badge-amber">⚠ API Key Required</span>
            )}
          </div>
        </div>

        <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '1.25rem', lineHeight: 1.6 }}>
          Google Gemini powers requirements scoring, INVEST criteria auditing, and Playwright test generation.
          Get your key from{' '}
          <a
            href="https://aistudio.google.com/app/apikey"
            target="_blank"
            rel="noreferrer"
            style={{ color: 'var(--color-primary)', fontWeight: 600 }}
          >
            Google AI Studio ↗
          </a>.
        </p>

        <form onSubmit={handleSaveGeminiSettings} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <div className="input-group">
            <label className="input-label">Select Gemini Model</label>
            <select
              className="input"
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              style={{ fontWeight: 600 }}
            >
              {AVAILABLE_MODELS.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.label} ({m.id})
                </option>
              ))}
            </select>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Tip: <strong>Gemini 3.5 Flash</strong> and <strong>3.1 Flash Lite</strong> are optimized for fast response times and generous free quotas.
            </span>
          </div>

          <div className="input-group">
            <label className="input-label">Gemini API Key</label>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <input
                type={showKey ? 'text' : 'password'}
                className="input"
                placeholder={settingsStatus.gemini_api_key_configured ? 'Paste new API Key to update...' : 'AIzaSy...'}
                value={apiKeyInput}
                onChange={(e) => setApiKeyInput(e.target.value)}
                style={{ flex: 1 }}
              />
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setShowKey(!showKey)}
                style={{ padding: '0.6rem 1rem' }}
              >
                {showKey ? 'Hide' : 'Show'}
              </button>
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? <><span className="spinner" style={{ width: 16, height: 16 }} /> Saving...</> : 'Save Settings'}
            </button>
          </div>
        </form>
      </div>

      {/* Section 2: JIRA Integration Status */}
      <div className="glass" style={{ padding: '1.75rem', marginBottom: '1.75rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <div style={{ fontSize: '1.5rem' }}>🔷</div>
            <div>
              <h3 style={{ fontSize: '1.05rem', margin: 0 }}>JIRA Cloud Connections</h3>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                {jiraConns.length} active connection{jiraConns.length === 1 ? '' : 's'}
              </span>
            </div>
          </div>
          <button className="btn btn-secondary" onClick={() => navigate('/onboarding')}>
            + Add Connection
          </button>
        </div>

        {jiraConns.length === 0 ? (
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>No JIRA connections configured yet.</p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {jiraConns.map((conn) => (
              <div key={conn.id} style={{ padding: '0.85rem 1rem', background: 'var(--color-surface-2)', borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div>
                  <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>{conn.site_name}</div>
                  <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>{conn.site_url}</div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                  <span className="badge badge-green">Connected</span>
                  <button
                    className="btn btn-secondary"
                    style={{ color: 'var(--color-rose)', borderColor: 'rgba(239, 68, 68, 0.2)', padding: '0.25rem 0.5rem', fontSize: '0.75rem' }}
                    onClick={() => handleRemoveJiraConnection(conn.id)}
                  >
                    Remove
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Section 3: GitHub Integration Status */}
      <div className="glass" style={{ padding: '1.75rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <div style={{ fontSize: '1.5rem' }}>🐙</div>
            <div>
              <h3 style={{ fontSize: '1.05rem', margin: 0 }}>GitHub Connections</h3>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                {ghConns.length} active connection{ghConns.length === 1 ? '' : 's'}
              </span>
            </div>
          </div>
          <button className="btn btn-secondary" onClick={() => navigate('/onboarding')}>
            + Add Connection
          </button>
        </div>

        {ghConns.length === 0 ? (
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>No GitHub connections configured yet.</p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {ghConns.map((conn) => (
              <div key={conn.id} style={{ padding: '0.85rem 1rem', background: 'var(--color-surface-2)', borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div>
                  <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>{conn.connection_name}</div>
                  <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>{conn.api_base_url}</div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                  <span className="badge badge-green">Connected</span>
                  <button
                    className="btn btn-secondary"
                    style={{ color: 'var(--color-rose)', borderColor: 'rgba(239, 68, 68, 0.2)', padding: '0.25rem 0.5rem', fontSize: '0.75rem' }}
                    onClick={() => handleRemoveGithubConnection(conn.id)}
                  >
                    Remove
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
