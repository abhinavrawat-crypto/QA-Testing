import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../services/api'
import { analysisService } from '../services/analysisService'

/* ---- helpers ---- */
const scoreColor = (v) => {
  if (v >= 80) return 'var(--color-emerald)'
  if (v >= 60) return 'var(--color-amber)'
  return 'var(--color-rose)'
}

const scoreLabel = (v) => {
  if (v >= 80) return 'Good'
  if (v >= 60) return 'Fair'
  return 'Poor'
}

const INVEST_LABELS = {
  independent: 'Independent',
  negotiable: 'Negotiable',
  valuable: 'Valuable',
  estimable: 'Estimable',
  small: 'Small',
  testable: 'Testable',
}

/* ---- Sub-components ---- */

function ScoreBar({ label, value }) {
  return (
    <div style={{ marginBottom: '0.65rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.3rem' }}>
        <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{label}</span>
        <span style={{ fontSize: '0.8rem', fontWeight: 600, color: scoreColor(value) }}>
          {value?.toFixed(0)}/100
        </span>
      </div>
      <div style={{ height: 6, background: 'var(--color-surface-3)', borderRadius: 99, overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${value}%`, background: scoreColor(value), borderRadius: 99, transition: 'width 0.6s ease' }} />
      </div>
    </div>
  )
}

function DiffPanel({ original, proposed, label, isEditing, editValue, onEdit }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
      {/* Original */}
      <div>
        <div style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--text-muted)', letterSpacing: '0.5px', textTransform: 'uppercase', marginBottom: '0.4rem' }}>
          Original {label}
        </div>
        <div style={{ background: 'rgba(244,63,94,0.05)', border: '1px solid rgba(244,63,94,0.15)', borderRadius: 'var(--radius-md)', padding: '0.75rem', minHeight: 80, fontSize: '0.85rem', color: 'var(--text-secondary)', whiteSpace: 'pre-wrap', lineHeight: 1.65 }}>
          {original || <em style={{ color: 'var(--text-muted)' }}>(empty)</em>}
        </div>
      </div>

      {/* Proposed / Editable */}
      <div>
        <div style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--text-muted)', letterSpacing: '0.5px', textTransform: 'uppercase', marginBottom: '0.4rem' }}>
          AI Proposed {label} <span style={{ color: 'var(--color-emerald)' }}>✓ editable</span>
        </div>
        {isEditing ? (
          <textarea
            value={editValue}
            onChange={(e) => onEdit(e.target.value)}
            style={{ width: '100%', minHeight: 80, background: 'rgba(16,185,129,0.05)', border: '1px solid rgba(16,185,129,0.3)', borderRadius: 'var(--radius-md)', padding: '0.75rem', fontSize: '0.85rem', color: 'var(--text-primary)', resize: 'vertical', fontFamily: 'inherit', lineHeight: 1.65 }}
          />
        ) : (
          <div style={{ background: 'rgba(16,185,129,0.05)', border: '1px solid rgba(16,185,129,0.15)', borderRadius: 'var(--radius-md)', padding: '0.75rem', minHeight: 80, fontSize: '0.85rem', color: 'var(--text-primary)', whiteSpace: 'pre-wrap', lineHeight: 1.65 }}>
            {proposed || <em style={{ color: 'var(--text-muted)' }}>(empty)</em>}
          </div>
        )}
      </div>
    </div>
  )
}

function splitClientText(rawDesc, rawAc) {
  let desc = rawDesc || ''
  let ac = rawAc || ''
  if (desc) {
    const match = desc.match(/(acceptance criteria(?:\s*\([^)]*\))?|ac\s*:)/i)
    if (match) {
      if (!ac) {
        ac = desc.substring(match.index).trim()
      }
      desc = desc.substring(0, match.index).trim()
    }
  }
  return { desc, ac }
}

function ScoreCard({ result, story, connectionId, onUpdated }) {
  const [expanded, setExpanded] = useState(false)
  const [editing, setEditing] = useState(false)
  const [edits, setEdits] = useState({ summary: '', description: '', ac: '' })
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState(null)

  const origTitle = result.summary || story?.summary || ''
  const rawDesc = result.original_description || result.description_text || story?.description_text || ''
  const rawAc = result.original_ac || result.acceptance_criteria || story?.acceptance_criteria || ''
  const { desc: origDesc, ac: origAc } = splitClientText(rawDesc, rawAc)

  const startEdit = () => {
    setEdits({
      summary: result.proposed_summary,
      description: result.proposed_description,
      ac: result.proposed_ac,
    })
    setEditing(true)
    setExpanded(true)
  }

  const approve = async () => {
    setLoading(true)
    setMessage(null)
    try {
      await analysisService.approveScore(result.id, connectionId, editing ? edits : {})
      setMessage({ type: 'success', text: `✓ Written back to JIRA ${result.jira_issue_key}` })
      onUpdated(result.id, 'approved')
    } catch (e) {
      setMessage({ type: 'error', text: e.response?.data?.detail || 'Approval failed' })
    } finally { setLoading(false) }
  }

  const reject = async () => {
    setLoading(true)
    try {
      await analysisService.rejectScore(result.id)
      setMessage({ type: 'info', text: 'Score rejected — no changes made to JIRA.' })
      onUpdated(result.id, 'rejected')
    } catch (e) {
      setMessage({ type: 'error', text: 'Reject failed' })
    } finally { setLoading(false) }
  }

  const isPending = result.approval_status === 'pending'
  const score = typeof result?.overall_score === 'number' ? result.overall_score : Number(result?.overall_score || 0)

  return (
    <div className="glass" style={{ marginBottom: '1rem', overflow: 'hidden', border: `1px solid ${score >= 80 ? 'rgba(16,185,129,0.2)' : score >= 60 ? 'rgba(245,158,11,0.2)' : 'rgba(244,63,94,0.2)'}` }}>
      {/* Header */}
      <div
        style={{ padding: '1.25rem 1.5rem', display: 'flex', alignItems: 'center', gap: '1rem', cursor: 'pointer' }}
        onClick={() => setExpanded(e => !e)}
      >
        {/* Score ring */}
        <div style={{ width: 56, height: 56, borderRadius: '50%', background: `conic-gradient(${scoreColor(score)} ${score * 3.6}deg, var(--color-surface-3) 0deg)`, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
          <div style={{ width: 42, height: 42, borderRadius: '50%', background: 'var(--color-surface)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.8rem', fontWeight: 800, color: scoreColor(score) }}>
            {score?.toFixed(0)}
          </div>
        </div>

        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ fontWeight: 700, color: 'var(--text-primary)' }}>{result.jira_issue_key}</span>
            <span className={`badge ${score >= 80 ? 'badge-green' : score >= 60 ? 'badge-amber' : 'badge-rose'}`} style={{ fontSize: '0.7rem' }}>
              {scoreLabel(score)}
            </span>
            {result.approval_status !== 'pending' && (
              <span className={`badge ${result.approval_status === 'approved' ? 'badge-green' : 'badge-rose'}`} style={{ fontSize: '0.7rem' }}>
                {result.approval_status}
              </span>
            )}
          </div>
          <p style={{ margin: '0.25rem 0 0', fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
            {origTitle}
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          {isPending && (
            <>
              <button className="btn btn-ghost" style={{ fontSize: '0.8rem', padding: '0.4rem 0.8rem' }} onClick={(e) => { e.stopPropagation(); startEdit() }}>
                ✏️ Edit
              </button>
              <button className="btn btn-primary" style={{ fontSize: '0.8rem', padding: '0.4rem 0.8rem' }} disabled={loading} onClick={(e) => { e.stopPropagation(); approve() }}>
                {loading ? <span className="spinner" style={{ width: 14, height: 14 }} /> : '✓ Approve'}
              </button>
              <button className="btn btn-secondary" style={{ fontSize: '0.8rem', padding: '0.4rem 0.8rem', color: 'var(--color-rose)' }} disabled={loading} onClick={(e) => { e.stopPropagation(); reject() }}>
                ✕ Reject
              </button>
            </>
          )}
          <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>{expanded ? '▲' : '▼'}</span>
        </div>
      </div>

      {message && (
        <div className={`alert alert-${message.type}`} style={{ margin: '0 1.5rem 1rem' }}>
          {message.text}
        </div>
      )}

      {/* Expanded content */}
      {expanded && (
        <div style={{ padding: '0 1.5rem 1.5rem', borderTop: '1px solid var(--color-border)' }}>
          {/* INVEST breakdown */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem', margin: '1.5rem 0' }}>
            <div>
              <h4 style={{ fontSize: '0.85rem', marginBottom: '1rem', color: 'var(--text-secondary)' }}>INVEST Breakdown</h4>
              {Object.entries(INVEST_LABELS).map(([key, label]) => (
                <ScoreBar key={key} label={label} value={result.invest_scores?.[key] ?? 0} />
              ))}
              {result.ac_score !== null && (
                <ScoreBar label="AC Completeness (Gherkin)" value={result.ac_score} />
              )}
            </div>

            {/* Gaps */}
            <div>
              <h4 style={{ fontSize: '0.85rem', marginBottom: '1rem', color: 'var(--text-secondary)' }}>Identified Gaps</h4>
              {result.gaps?.length > 0 ? (
                result.gaps.map((g, i) => (
                  <div key={i} style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.5rem', fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: 1.55 }}>
                    <span style={{ color: 'var(--color-rose)', flexShrink: 0 }}>⚠</span>
                    {g}
                  </div>
                ))
              ) : (
                <p style={{ fontSize: '0.82rem', color: 'var(--color-emerald)' }}>✓ No major gaps identified</p>
              )}
            </div>
          </div>

          {/* Diff panels */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            <div>
              <h4 style={{ fontSize: '0.85rem', marginBottom: '0.75rem', color: 'var(--text-secondary)' }}>Story Title</h4>
              <DiffPanel
                original={origTitle}
                proposed={editing ? edits.summary : result.proposed_summary}
                label="Title"
                isEditing={editing}
                editValue={edits.summary}
                onEdit={(v) => setEdits(e => ({ ...e, summary: v }))}
              />
            </div>
            <div>
              <h4 style={{ fontSize: '0.85rem', marginBottom: '0.75rem', color: 'var(--text-secondary)' }}>Description</h4>
              <DiffPanel
                original={origDesc}
                proposed={editing ? edits.description : result.proposed_description}
                label="Description"
                isEditing={editing}
                editValue={edits.description}
                onEdit={(v) => setEdits(e => ({ ...e, description: v }))}
              />
            </div>
            <div>
              <h4 style={{ fontSize: '0.85rem', marginBottom: '0.75rem', color: 'var(--text-secondary)' }}>Acceptance Criteria (Gherkin)</h4>
              <DiffPanel
                original={origAc}
                proposed={editing ? edits.ac : result.proposed_ac}
                label="Acceptance Criteria"
                isEditing={editing}
                editValue={edits.ac}
                onEdit={(v) => setEdits(e => ({ ...e, ac: v }))}
              />
            </div>
          </div>

          {editing && isPending && (
            <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1.25rem' }}>
              <button className="btn btn-primary" disabled={loading} onClick={approve} style={{ fontSize: '0.875rem' }}>
                {loading ? <><span className="spinner" style={{ width: 14, height: 14 }} /> Writing to JIRA…</> : '✓ Approve & write to JIRA'}
              </button>
              <button className="btn btn-secondary" onClick={() => setEditing(false)} style={{ fontSize: '0.875rem' }}>
                Cancel edit
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

const formatErrorMsg = (err) => {
  if (!err) return 'Operation failed'
  if (typeof err === 'string') return err
  if (typeof err === 'object') {
    if (err.detail) {
      if (typeof err.detail === 'string') return err.detail
      if (typeof err.detail === 'object') {
        if (err.detail.scoring_errors && Array.isArray(err.detail.scoring_errors)) {
          return err.detail.scoring_errors.map(e => `${e.story_id}: ${e.error}`).join('; ')
        }
        return JSON.stringify(err.detail)
      }
    }
    if (err.message) return err.message
    return JSON.stringify(err)
  }
  return String(err)
}

/* ---- Main Page ---- */
export default function StoryScoring() {
  const navigate = useNavigate()
  const [jiraConns, setJiraConns] = useState([])
  const [selectedConn, setSelectedConn] = useState('')
  const [projects, setProjects] = useState([])
  const [selectedProject, setSelectedProject] = useState('')
  const [stories, setStories] = useState([])
  const [selectedStories, setSelectedStories] = useState([])
  const [scoreResults, setScoreResults] = useState([])
  const [loadingProjects, setLoadingProjects] = useState(false)
  const [loadingStories, setLoadingStories] = useState(false)
  const [loadingScore, setLoadingScore] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    api.get('/jira/connections').then(r => {
      setJiraConns(r.data)
      if (r.data.length === 1) setSelectedConn(r.data[0].id)
    }).catch(e => setError(formatErrorMsg(e.response?.data || e.message)))
  }, [])

  const syncProjects = async () => {
    if (!selectedConn) return
    setLoadingProjects(true); setError('')
    try {
      const r = await api.post(`/jira/connections/${selectedConn}/sync-projects`)
      setProjects(r.data)
    } catch (e) { setError(formatErrorMsg(e.response?.data || 'Failed to fetch projects')) }
    finally { setLoadingProjects(false) }
  }

  const syncStories = async () => {
    if (!selectedProject || !selectedConn) return
    setLoadingStories(true); setError('')
    try {
      const r = await api.post(`/jira/connections/${selectedConn}/projects/${selectedProject}/sync-stories`)
      setStories(r.data)
      setSelectedStories([])
    } catch (e) { setError(formatErrorMsg(e.response?.data || 'Failed to fetch stories')) }
    finally { setLoadingStories(false) }
  }

  const toggleStory = (id) => setSelectedStories(s =>
    s.includes(id) ? s.filter(x => x !== id) : [...s, id]
  )

  const runScoring = async () => {
    if (!selectedStories.length || !selectedConn) return
    setLoadingScore(true); setError(''); setScoreResults([])
    try {
      const r = await analysisService.scoreStories(selectedStories, selectedConn)
      setScoreResults(r.data || [])
    } catch (e) { setError(formatErrorMsg(e.response?.data || e.message || 'Scoring failed')) }
    finally { setLoadingScore(false) }
  }

  const handleUpdated = (scoreId, newStatus) => {
    setScoreResults(prev => prev.map(r => r.id === scoreId ? { ...r, approval_status: newStatus } : r))
  }

  return (
    <div style={{ padding: '2rem', maxWidth: '1400px', margin: '0 auto' }}>
      <div style={{ marginBottom: '2rem' }}>
        <span className="badge badge-blue" style={{ marginBottom: '0.5rem' }}>Requirements Scoring</span>
        <h2 style={{ marginBottom: '0.4rem' }}>User Story Quality Scoring</h2>
        <p style={{ fontSize: '0.9rem' }}>Select JIRA stories to score against INVEST + Gherkin AC criteria. Review and approve AI-proposed rewrites.</p>
      </div>

      {error && (
        <div className="alert alert-error" style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem' }}>
          <div>⚠ {error}</div>
          {error.includes('Gemini API Key') && (
            <button className="btn btn-primary" onClick={() => navigate('/settings')} style={{ fontSize: '0.825rem', padding: '0.4rem 0.9rem' }}>
              ⚙️ Go to Settings →
            </button>
          )}
        </div>
      )}

      {/* Step 1 — Select connection + project */}
      <div className="glass" style={{ padding: '1.5rem', marginBottom: '1.5rem' }}>
        <h3 style={{ fontSize: '0.9rem', marginBottom: '1rem', color: 'var(--text-secondary)' }}>1 — Select JIRA connection & project</h3>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr auto', gap: '1rem', alignItems: 'end' }}>
          <div className="input-group">
            <label className="input-label">JIRA Connection</label>
            <select className="input" value={selectedConn} onChange={e => { setSelectedConn(e.target.value); setProjects([]); setStories([]) }}>
              <option value="">Select connection…</option>
              {jiraConns.map(c => <option key={c.id} value={c.id}>{c.site_name}</option>)}
            </select>
          </div>
          <div className="input-group">
            <label className="input-label">Project</label>
            <select className="input" value={selectedProject} onChange={e => { setSelectedProject(e.target.value); setStories([]) }}>
              <option value="">Select project…</option>
              {projects.map(p => <option key={p.id} value={p.project_key}>{p.name} ({p.project_key})</option>)}
            </select>
          </div>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button className="btn btn-secondary" onClick={syncProjects} disabled={!selectedConn || loadingProjects} style={{ whiteSpace: 'nowrap' }}>
              {loadingProjects ? <span className="spinner" style={{ width: 14, height: 14 }} /> : '↻ Load projects'}
            </button>
            <button className="btn btn-secondary" onClick={syncStories} disabled={!selectedProject || loadingStories} style={{ whiteSpace: 'nowrap' }}>
              {loadingStories ? <span className="spinner" style={{ width: 14, height: 14 }} /> : '↻ Load stories'}
            </button>
          </div>
        </div>
      </div>

      {/* Step 2 — Select stories */}
      {stories.length > 0 && (
        <div className="glass" style={{ padding: '1.5rem', marginBottom: '1.5rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <h3 style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
              2 — Select stories to score ({selectedStories.length} selected)
            </h3>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button className="btn btn-ghost" style={{ fontSize: '0.8rem' }} onClick={() => setSelectedStories(stories.map(s => s.id))}>Select all</button>
              <button className="btn btn-ghost" style={{ fontSize: '0.8rem' }} onClick={() => setSelectedStories([])}>Clear</button>
            </div>
          </div>

          <div style={{ maxHeight: 320, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
            {stories.map(s => (
              <label key={s.id} style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '0.6rem 0.75rem', borderRadius: 'var(--radius-sm)', background: selectedStories.includes(s.id) ? 'var(--color-primary-glow)' : 'transparent', cursor: 'pointer', border: `1px solid ${selectedStories.includes(s.id) ? 'rgba(91,138,240,0.3)' : 'transparent'}`, transition: 'var(--transition)' }}>
                <input type="checkbox" checked={selectedStories.includes(s.id)} onChange={() => toggleStory(s.id)} style={{ accentColor: 'var(--color-primary)' }} />
                <span style={{ fontSize: '0.8rem', color: 'var(--color-primary)', fontWeight: 600, minWidth: 80 }}>{s.jira_issue_key}</span>
                <span style={{ fontSize: '0.875rem', color: 'var(--text-primary)', flex: 1 }}>{s.summary}</span>
                {s.status && <span className="badge badge-blue" style={{ fontSize: '0.7rem' }}>{s.status}</span>}
                {s.latest_score !== null && s.latest_score !== undefined && (
                  <span style={{ fontSize: '0.75rem', color: scoreColor(s.latest_score), fontWeight: 600 }}>
                    {s.latest_score?.toFixed(0)}/100
                  </span>
                )}
              </label>
            ))}
          </div>

          <div style={{ marginTop: '1rem', display: 'flex', justifyContent: 'flex-end' }}>
            <button className="btn btn-primary" disabled={!selectedStories.length || loadingScore} onClick={runScoring}>
              {loadingScore ? (
                <><span className="spinner" style={{ width: 16, height: 16 }} /> Scoring with Gemini…</>
              ) : (
                `⭐ Score ${selectedStories.length} ${selectedStories.length === 1 ? 'story' : 'stories'}`
              )}
            </button>
          </div>
        </div>
      )}

      {/* Step 3 — Results */}
      {scoreResults.length > 0 && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <h3 style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
              3 — Review & approve AI suggestions ({scoreResults.length} scored)
            </h3>
            <div style={{ display: 'flex', gap: '0.5rem', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              <span style={{ color: 'var(--color-emerald)' }}>● {scoreResults.filter(r => r.approval_status === 'approved').length} approved</span>
              <span style={{ color: 'var(--color-rose)' }}>● {scoreResults.filter(r => r.approval_status === 'rejected').length} rejected</span>
              <span>● {scoreResults.filter(r => r.approval_status === 'pending').length} pending</span>
            </div>
          </div>
          {scoreResults.map(r => (
            <ScoreCard
              key={r.id}
              result={r}
              story={stories.find(s => s.id === r.story_id || s.jira_issue_key === r.jira_issue_key)}
              connectionId={selectedConn}
              onUpdated={handleUpdated}
            />
          ))}
        </div>
      )}
    </div>
  )
}
