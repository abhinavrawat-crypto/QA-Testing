import { useState, useEffect } from 'react'
import api from '../services/api'
import { discoveryService } from '../services/discoveryService'

export default function StoryDiscovery() {
  const [ghConns, setGhConns] = useState([])
  const [selectedGhConn, setSelectedGhConn] = useState('')
  const [repos, setRepos] = useState([])
  const [selectedRepos, setSelectedRepos] = useState([])
  const [jiraConns, setJiraConns] = useState([])
  const [selectedJiraConn, setSelectedJiraConn] = useState('')
  const [jiraProjects, setJiraProjects] = useState([])
  const [selectedProject, setSelectedProject] = useState('')
  const [issueType, setIssueType] = useState('Story')
  const [threshold, setThreshold] = useState(0.5)

  const [loadingRepos, setLoadingRepos] = useState(false)
  const [discovering, setDiscovering] = useState(false)
  const [batchCreating, setBatchCreating] = useState(false)
  const [results, setResults] = useState([])
  const [error, setError] = useState('')
  const [creatingJiraKey, setCreatingJiraKey] = useState(null)
  const [successMsg, setSuccessMsg] = useState('')

  useEffect(() => {
    api.get('/github/connections').then(r => { setGhConns(r.data); if (r.data.length === 1) setSelectedGhConn(r.data[0].id) })
    api.get('/jira/connections').then(r => { setJiraConns(r.data); if (r.data.length === 1) setSelectedJiraConn(r.data[0].id) })
  }, [])

  const loadRepos = async () => {
    if (!selectedGhConn) return
    setLoadingRepos(true)
    try {
      const r = await api.post(`/github/connections/${selectedGhConn}/sync-repos`)
      setRepos(r.data)
    } catch (e) { setError(e.response?.data?.detail || 'Failed to load repos') }
    finally { setLoadingRepos(false) }
  }

  const loadJiraProjects = async () => {
    if (!selectedJiraConn) return
    try {
      const r = await api.post(`/jira/connections/${selectedJiraConn}/sync-projects`)
      setJiraProjects(r.data)
      if (r.data.length > 0) setSelectedProject(r.data[0].project_key)
    } catch (e) { setError('Failed to load JIRA projects') }
  }

  const runDiscovery = async () => {
    if (!selectedRepos.length) return
    setDiscovering(true); setError(''); setSuccessMsg(''); setResults([])
    try {
      const r = await discoveryService.discoverUnmatched(selectedRepos, parseFloat(threshold))
      setResults(r.data)
    } catch (e) { setError(e.response?.data?.detail || 'Discovery failed') }
    finally { setDiscovering(false) }
  }

  const handleUpdateDraft = (testCaseId, field, val) => {
    setResults(prev => prev.map(item => {
      if (item.test_case_id === testCaseId && item.draft_story) {
        return {
          ...item,
          draft_story: {
            ...item.draft_story,
            [field]: val,
          }
        }
      }
      return item
    }))
  }

  const handleCreateJiraStory = async (item) => {
    if (!selectedJiraConn || !selectedProject) {
      setError('Please select a JIRA Connection and Project in settings above.')
      return
    }
    setCreatingJiraKey(item.test_case_id)
    setError(''); setSuccessMsg('')
    try {
      const res = await discoveryService.createJiraStory(
        selectedJiraConn,
        selectedProject,
        item.draft_story,
        issueType
      )
      setSuccessMsg(`✓ Created JIRA Issue ${res.data.key} for test "${item.test_title}"`)
      setResults(prev => prev.map(r => r.test_case_id === item.test_case_id ? {
        ...r,
        status: 'created',
        created_jira_key: res.data.key
      } : r))
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to create JIRA issue')
    } finally {
      setCreatingJiraKey(null)
    }
  }

  const handleBatchCreate = async () => {
    const unmatchedItems = results.filter(r => r.status === 'unmatched')
    if (!unmatchedItems.length) return
    setBatchCreating(true); setError(''); setSuccessMsg('')
    let createdCount = 0

    for (const item of unmatchedItems) {
      try {
        const res = await discoveryService.createJiraStory(
          selectedJiraConn,
          selectedProject,
          item.draft_story,
          issueType
        )
        createdCount++
        setResults(prev => prev.map(r => r.test_case_id === item.test_case_id ? {
          ...r,
          status: 'created',
          created_jira_key: res.data.key
        } : r))
      } catch (e) {
        console.error('Batch item error', e)
      }
    }
    setSuccessMsg(`🎉 Successfully batch-created ${createdCount} issues in JIRA!`)
    setBatchCreating(false)
  }

  const toggleRepo = (id) => setSelectedRepos(s => s.includes(id) ? s.filter(x => x !== id) : [...s, id])

  const unmatchedCount = results.filter(r => r.status === 'unmatched').length
  const matchedCount = results.filter(r => r.status === 'matched').length

  return (
    <div style={{ padding: '2rem', maxWidth: '1400px', margin: '0 auto' }}>
      <div style={{ marginBottom: '2rem' }}>
        <h2 style={{ marginBottom: '0.4rem' }}>Unmatched Test Discovery</h2>
        <p style={{ fontSize: '0.9rem' }}>Scan test repos to find automated tests without matching JIRA user stories. Generate, edit, and push new INVEST stories directly to JIRA.</p>
      </div>

      {error && <div className="alert alert-error" style={{ marginBottom: '1.5rem' }}>⚠ {error}</div>}
      {successMsg && <div className="alert alert-success" style={{ marginBottom: '1.5rem' }}>{successMsg}</div>}

      {/* Setup panel */}
      <div className="glass" style={{ padding: '1.5rem', marginBottom: '1.5rem' }}>
        <h3 style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>1 — Select Repositories & JIRA Target</h3>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
          <div>
            <label className="input-label">GitHub Connection</label>
            <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.75rem' }}>
              <select className="input" style={{ flex: 1 }} value={selectedGhConn} onChange={e => setSelectedGhConn(e.target.value)}>
                <option value="">Select connection…</option>
                {ghConns.map(c => <option key={c.id} value={c.id}>{c.connection_name}</option>)}
              </select>
              <button className="btn btn-secondary" onClick={loadRepos} disabled={!selectedGhConn || loadingRepos}>
                {loadingRepos ? <span className="spinner" style={{ width: 12, height: 12 }} /> : 'Load Repos'}
              </button>
            </div>
            <div style={{ maxHeight: 180, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
              {repos.map(r => (
                <label key={r.id} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.4rem 0.6rem', borderRadius: 'var(--radius-sm)', background: selectedRepos.includes(r.id) ? 'rgba(20,184,166,0.08)' : 'transparent', border: `1px solid ${selectedRepos.includes(r.id) ? 'rgba(20,184,166,0.3)' : 'transparent'}`, cursor: 'pointer' }}>
                  <input type="checkbox" checked={selectedRepos.includes(r.id)} onChange={() => toggleRepo(r.id)} style={{ accentColor: 'var(--color-teal)' }} />
                  <span style={{ fontSize: '0.82rem', color: 'var(--text-primary)' }}>{r.name}</span>
                </label>
              ))}
            </div>
          </div>

          <div>
            <label className="input-label">JIRA Target Project & Settings</label>
            <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.75rem' }}>
              <select className="input" style={{ flex: 1 }} value={selectedJiraConn} onChange={e => { setSelectedJiraConn(e.target.value); loadJiraProjects() }}>
                <option value="">JIRA Connection…</option>
                {jiraConns.map(c => <option key={c.id} value={c.id}>{c.site_name}</option>)}
              </select>
              <button className="btn btn-secondary" onClick={loadJiraProjects} disabled={!selectedJiraConn}>Load Projects</button>
            </div>
            {jiraProjects.length > 0 && (
              <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '0.5rem', marginBottom: '0.75rem' }}>
                <div className="input-group">
                  <label className="input-label">Target Project</label>
                  <select className="input" value={selectedProject} onChange={e => setSelectedProject(e.target.value)}>
                    {jiraProjects.map(p => <option key={p.id} value={p.project_key}>{p.name} ({p.project_key})</option>)}
                  </select>
                </div>
                <div className="input-group">
                  <label className="input-label">Issue Type</label>
                  <select className="input" value={issueType} onChange={e => setIssueType(e.target.value)}>
                    <option value="Story">Story</option>
                    <option value="Task">Task</option>
                    <option value="Bug">Bug</option>
                  </select>
                </div>
              </div>
            )}
            <div className="input-group">
              <label className="input-label">Matching Similarity Cutoff ({Math.round(threshold * 100)}%)</label>
              <input type="range" min="0.3" max="1.0" step="0.05" value={threshold} onChange={e => setThreshold(e.target.value)} style={{ accentColor: 'var(--color-teal)' }} />
            </div>
          </div>
        </div>

        <div style={{ marginTop: '1.25rem', display: 'flex', justifyContent: 'flex-end' }}>
          <button className="btn btn-primary" disabled={!selectedRepos.length || discovering} onClick={runDiscovery} style={{ background: 'var(--color-teal)', color: '#000' }}>
            {discovering ? <><span className="spinner" style={{ width: 16, height: 16 }} /> Scanning Vector Index…</> : `🗺️ Scan ${selectedRepos.length} Repos for Unmatched Tests`}
          </button>
        </div>
      </div>

      {/* Results */}
      {results.length > 0 && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
            <h3 style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
              Discovery Results ({results.length} tests scanned)
            </h3>
            <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
              <span style={{ fontSize: '0.8rem', color: 'var(--color-amber)' }}>● {unmatchedCount} unmatched</span>
              <span style={{ fontSize: '0.8rem', color: 'var(--color-emerald)' }}>● {matchedCount} matched</span>
              {unmatchedCount > 0 && (
                <button
                  className="btn btn-secondary"
                  style={{ fontSize: '0.8rem', padding: '0.35rem 0.8rem', color: 'var(--color-teal)', borderColor: 'rgba(45,212,191,0.3)' }}
                  disabled={batchCreating}
                  onClick={handleBatchCreate}
                >
                  {batchCreating ? <><span className="spinner" style={{ width: 12, height: 12 }} /> Batch Creating…</> : `⚡ Batch Create All ${unmatchedCount} Stories in JIRA`}
                </button>
              )}
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(520px, 1fr))', gap: '1.5rem' }}>
            {results.map((item, idx) => (
              <div key={idx} className="glass" style={{ display: 'flex', flexDirection: 'column', padding: '1.25rem', borderLeft: `4px solid ${item.status === 'unmatched' ? 'var(--color-amber)' : 'var(--color-emerald)'}` }}>
                {/* Header */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem', gap: '0.5rem' }}>
                  <div style={{ flex: 1, overflow: 'hidden' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '0.25rem' }}>
                      <span style={{ fontWeight: 600, fontSize: '0.95rem', color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '320px' }} title={item.test_title}>
                        {item.test_title}
                      </span>
                      <span className={`badge ${item.status === 'unmatched' ? 'badge-amber' : item.status === 'created' ? 'badge-green' : 'badge-green'}`}>
                        {item.status === 'unmatched' ? 'Unmatched' : item.status === 'created' ? 'Created' : 'Matched'}
                      </span>
                      <span className="badge badge-purple" style={{ fontSize: '0.7rem' }}>{item.test_type}</span>
                    </div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={item.file_path}>
                      {item.file_path}
                    </div>
                  </div>
                </div>

                {/* Main Content Body */}
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '0.75rem', marginBottom: '1rem' }}>
                  {item.status === 'matched' && (
                    <div style={{ background: 'rgba(16,185,129,0.05)', padding: '0.85rem', borderRadius: 'var(--radius-md)', fontSize: '0.82rem', color: 'var(--text-secondary)', border: '1px solid rgba(16,185,129,0.15)', height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                      <div style={{ fontWeight: 600, color: 'var(--color-emerald)', marginBottom: '0.25rem' }}>✓ Matched existing issue</div>
                      <div><strong>{item.matched_story_key}</strong> — {item.matched_story_summary}</div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.5rem' }}>Similarity Score: {(item.similarity_score * 100).toFixed(0)}%</div>
                    </div>
                  )}

                  {item.status === 'created' && (
                    <div style={{ background: 'rgba(16,185,129,0.08)', padding: '1rem', borderRadius: 'var(--radius-md)', fontSize: '0.85rem', color: 'var(--color-emerald)', fontWeight: 600, border: '1px solid rgba(16,185,129,0.2)', height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'center', textAlign: 'center' }}>
                      🎉 Issue created in JIRA!
                      <div style={{ fontSize: '1.1rem', marginTop: '0.5rem' }}>
                        <strong style={{ color: 'var(--color-emerald)' }}>{item.created_jira_key}</strong>
                      </div>
                    </div>
                  )}

                  {item.draft_story && item.status === 'unmatched' && (
                    <div style={{ background: 'var(--color-surface-2)', padding: '1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--color-border)' }}>
                      <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--color-teal)', textTransform: 'uppercase', marginBottom: '0.6rem' }}>
                        🤖 AI Drafted JIRA {issueType} (Editable)
                      </div>

                      <div className="input-group" style={{ marginBottom: '0.6rem' }}>
                        <label className="input-label" style={{ fontSize: '0.72rem' }}>Summary</label>
                        <input
                          className="input"
                          style={{ fontSize: '0.82rem', padding: '0.5rem 0.75rem' }}
                          value={item.draft_story.summary}
                          onChange={e => handleUpdateDraft(item.test_case_id, 'summary', e.target.value)}
                        />
                      </div>

                      <div className="input-group" style={{ marginBottom: '0.6rem' }}>
                        <label className="input-label" style={{ fontSize: '0.72rem' }}>Description</label>
                        <textarea
                          className="input"
                          style={{ height: 60, fontSize: '0.8rem', padding: '0.5rem 0.75rem', resize: 'vertical' }}
                          value={item.draft_story.description}
                          onChange={e => handleUpdateDraft(item.test_case_id, 'description', e.target.value)}
                        />
                      </div>

                      <div className="input-group">
                        <label className="input-label" style={{ fontSize: '0.72rem' }}>Gherkin Acceptance Criteria</label>
                        <textarea
                          className="input"
                          style={{ height: 80, fontFamily: 'JetBrains Mono, monospace', fontSize: '0.76rem', padding: '0.5rem 0.75rem', resize: 'vertical' }}
                          value={item.draft_story.acceptance_criteria}
                          onChange={e => handleUpdateDraft(item.test_case_id, 'acceptance_criteria', e.target.value)}
                        />
                      </div>
                    </div>
                  )}
                </div>

                {/* Footer Action */}
                {item.status === 'unmatched' && (
                  <div style={{ borderTop: '1px solid var(--color-border)', paddingTop: '0.75rem', display: 'flex', justifyContent: 'flex-end' }}>
                    <button
                      className="btn btn-primary"
                      style={{ fontSize: '0.8rem', padding: '0.45rem 1rem', background: 'var(--color-teal)', color: '#000', boxShadow: 'none' }}
                      disabled={creatingJiraKey === item.test_case_id}
                      onClick={() => handleCreateJiraStory(item)}
                    >
                      {creatingJiraKey === item.test_case_id ? <span className="spinner" style={{ width: 12, height: 12 }} /> : `+ Create JIRA ${issueType}`}
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
