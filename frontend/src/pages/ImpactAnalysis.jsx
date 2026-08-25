import { useState, useEffect } from 'react'
import { createPortal } from 'react-dom'
import api from '../services/api'
import { indexingService, impactService } from '../services/impactService'
import { codeGenService } from '../services/discoveryService'
import { runnerService } from '../services/runnerService'

/* ---- Confidence badge ---- */
const confBadge = (c) => {
  const pct = Math.round((c || 0) * 100)
  const cls = pct >= 70 ? 'badge-green' : pct >= 40 ? 'badge-amber' : 'badge-rose'
  return <span className={`badge ${cls}`} style={{ fontSize: '0.7rem' }}>{pct}% confidence</span>
}

/* ---- Impact result card per story ---- */
function StoryImpactCard({ storyResult, selectedGhConn, selectedRepoFullName, selectedJiraConn }) {
  const { story_key, story_summary, story_id, impacted = [], missing_coverage = [], unaffected = [], gaps = [] } = storyResult

  const [genModal, setGenModal] = useState(null) // { title, scenario, original, isGap }
  const [generatedCode, setGeneratedCode] = useState('')
  const [explanation, setExplanation] = useState('')
  const [targetPath, setTargetPath] = useState('')
  const [lang, setLang] = useState('typescript')
  const [isDraft, setIsDraft] = useState(false)
  const [customTitle, setCustomTitle] = useState('')
  const [copied, setCopied] = useState(false)

  const [pushingJira, setPushingJira] = useState(null)
  const [jiraFeedback, setJiraFeedback] = useState({})
  const [copyFeedback, setCopyFeedback] = useState({})

  const [targetUrl, setTargetUrl] = useState('')
  const [envInput, setEnvInput] = useState('')
  const [isHeaded, setIsHeaded] = useState(true)

  const [generating, setGenerating] = useState(false)
  const [creatingPR, setCreatingPR] = useState(false)
  const [runningSandbox, setRunningSandbox] = useState(false)
  const [runLogs, setRunLogs] = useState([])
  const [runStatus, setRunStatus] = useState(null)
  const [prResult, setPrResult] = useState(null)
  const [genError, setGenError] = useState('')

  const handleCopyProposed = (content, itemId) => {
    if (!content) return
    navigator.clipboard.writeText(content)
    setCopyFeedback(prev => ({ ...prev, [itemId]: true }))
    setTimeout(() => {
      setCopyFeedback(prev => ({ ...prev, [itemId]: false }))
    }, 2000)
  }

  const handlePushToJira = async (itemId, impactSummary, proposedContent) => {
    if (!selectedJiraConn) {
      setJiraFeedback(prev => ({ ...prev, [itemId]: '⚠ Select a JIRA Connection in Step 1 first' }))
      return
    }
    setPushingJira(itemId)
    try {
      await api.post('/jira/stories/push-impact', {
        connection_id: selectedJiraConn,
        issue_key: story_key,
        impact_summary: impactSummary,
        proposed_content: proposedContent,
      })
      setJiraFeedback(prev => ({ ...prev, [itemId]: '🎉 Successfully pushed comment to JIRA ticket!' }))
    } catch (e) {
      setJiraFeedback(prev => ({ ...prev, [itemId]: `⚠ ${e.response?.data?.detail || 'Push to JIRA failed'}` }))
    } finally {
      setPushingJira(null)
    }
  }

  const handleRunSandbox = async () => {
    if (!generatedCode) return
    if (!targetUrl.trim()) {
      setGenError('Please enter your Target Application URL (e.g. http://localhost:3000 or http://localhost:5173) in the "Target Base URL" field below so the test knows where to run.')
      return
    }
    setRunningSandbox(true); setGenError(''); setRunLogs([]); setRunStatus('running')
    
    const envVars = {}
    if (envInput.trim()) {
      envInput.split('\n').forEach(line => {
        const parts = line.split('=')
        if (parts.length >= 2) {
          envVars[parts[0].trim()] = parts.slice(1).join('=').trim()
        }
      })
    }

    try {
      const res = await runnerService.executeTest(generatedCode, targetUrl || null, Object.keys(envVars).length ? envVars : null, isHeaded)
      setRunLogs(res.data.logs || [])
      setRunStatus(res.data.status)
    } catch (e) {
      setGenError(e.response?.data?.detail || 'Live execution failed')
      setRunStatus('failed')
    } finally {
      setRunningSandbox(false)
    }
  }

  const handleOpenGen = async (title, scenario, original, isGap, selectedLang = lang) => {
    setGenModal({ title, scenario, original, isGap })
    setGenerating(true); setGenError(''); setPrResult(null); setCopied(false)
    const ext = selectedLang === 'typescript' ? '.spec.ts' : '.spec.js'
    const defaultPath = isGap ? `tests/gaps${ext}` : `tests/updated${ext}`
    setTargetPath(defaultPath)
    try {
      const res = await codeGenService.generateCode(story_id, original, scenario, defaultPath, selectedLang, targetUrl || null)
      setGeneratedCode(res.data.generated_code)
      setExplanation(res.data.explanation)
      if (res.data.file_path) setTargetPath(res.data.file_path)
    } catch (e) {
      setGenError(e.response?.data?.detail || 'Code generation failed')
    } finally {
      setGenerating(false)
    }
  }

  const handleCopyCode = () => {
    navigator.clipboard.writeText(generatedCode)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleCreatePR = async () => {
    if (!selectedGhConn || !selectedRepoFullName) {
      setGenError('Please select a GitHub connection and repository first.')
      return
    }
    setCreatingPR(true); setGenError('')
    try {
      const res = await codeGenService.createPR(
        selectedGhConn,
        selectedRepoFullName,
        targetPath,
        generatedCode,
        story_key,
        isDraft,
        customTitle || null
      )
      setPrResult(res.data)
    } catch (e) {
      setGenError(e.response?.data?.detail || 'PR creation failed')
    } finally {
      setCreatingPR(false)
    }
  }

  const isNotCovered = gaps.length > 0 || (storyResult.not_covered && storyResult.not_covered.is_not_covered)
  const totalImpacted = impacted.length + missing_coverage.length

  const getInitialTab = () => {
    if (totalImpacted > 0) return 'impacted'
    if (isNotCovered) return 'not_covered'
    return 'not_impacted'
  }

  const [tab, setTab] = useState(getInitialTab())

  useEffect(() => {
    setTab(getInitialTab())
  }, [storyResult])

  useEffect(() => {
    if (genModal) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = 'unset'
    }
    return () => {
      document.body.style.overflow = 'unset'
    }
  }, [genModal])

  const tabs = [
    { id: 'impacted', label: `Impacted (${totalImpacted})`, color: 'var(--color-amber)', count: totalImpacted },
    { id: 'not_covered', label: `Not Covered (${isNotCovered ? 1 : 0})`, color: 'var(--color-purple)', count: isNotCovered ? 1 : 0 },
    { id: 'not_impacted', label: `Not Impacted (${unaffected.length})`, color: 'var(--color-emerald)', count: unaffected.length },
  ]

  return (
    <div className="glass" style={{ marginBottom: '1.25rem', overflow: 'hidden' }}>
      {/* Story header */}
      <div style={{ padding: '1.25rem 1.5rem', borderBottom: '1px solid var(--color-border)', display: 'flex', alignItems: 'center', gap: '1rem' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
            <span style={{ fontWeight: 700, color: 'var(--color-primary)' }}>{story_key}</span>
            {totalImpacted > 0 && <span className="badge badge-amber" style={{ fontSize: '0.7rem' }}>{totalImpacted} Impacted</span>}
            {isNotCovered && <span className="badge badge-rose" style={{ fontSize: '0.7rem' }}>Not Covered</span>}
            <span className="badge badge-green" style={{ fontSize: '0.7rem' }}>{unaffected.length} Not Impacted</span>
          </div>
          <p style={{ fontSize: '0.875rem', margin: '0.2rem 0 0', color: 'var(--text-secondary)' }}>{story_summary}</p>
        </div>
      </div>

      {/* Level 1 Verdict Tabs */}
      <div style={{ display: 'flex', borderBottom: '1px solid var(--color-border)', padding: '0 1.5rem', background: 'rgba(0,0,0,0.02)' }}>
        {tabs.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            style={{
              padding: '0.75rem 1rem',
              background: 'none',
              border: 'none',
              borderBottom: tab === t.id ? `2px solid ${t.color}` : '2px solid transparent',
              color: tab === t.id ? t.color : 'var(--text-secondary)',
              fontWeight: tab === t.id ? 600 : 400,
              fontSize: '0.85rem',
              cursor: 'pointer',
              transition: 'var(--transition)',
              marginBottom: -1,
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Level 1 Verdict Content */}
      <div style={{ padding: '1.25rem 1.5rem' }}>
        {/* LEVEL 1: IMPACTED (NEEDS_UPDATE & NEEDS_EXTENSION) */}
        {tab === 'impacted' && (
          totalImpacted === 0 ? (
            <p style={{ fontSize: '0.875rem', color: 'var(--color-emerald)' }}>✓ No existing test files are impacted by this story.</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {/* NEEDS_UPDATE Sub-tag items */}
              {impacted.map((item, i) => {
                const itemId = `update-${i}`
                const proposedText = item.suggested_change || ''
                return (
                  <div key={itemId} style={{ padding: '1.1rem', background: 'rgba(245,158,11,0.04)', border: '1px solid rgba(245,158,11,0.2)', borderRadius: 'var(--radius-md)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.5rem', flexWrap: 'wrap' }}>
                      <span style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-primary)' }}>{item.test_title}</span>
                      <span className="badge badge-amber" style={{ fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Level 2: NEEDS_UPDATE</span>
                      {item.file_path && <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>({item.file_path})</span>}
                      {confBadge(item.confidence)}
                    </div>
                    <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: '0.75rem' }}>
                      <strong>Rationale:</strong> {item.rationale}
                    </p>
                    
                    {/* Scenario Diff View */}
                    <div style={{ display: 'grid', gridTemplateColumns: item.original_scenario ? '1fr 1fr' : '1fr', gap: '0.75rem', marginBottom: '0.75rem' }}>
                      {item.original_scenario && (
                        <div style={{ background: 'rgba(239, 68, 68, 0.06)', border: '1px solid rgba(239, 68, 68, 0.2)', borderRadius: 'var(--radius-sm)', padding: '0.6rem 0.75rem' }}>
                          <div style={{ fontSize: '0.7rem', fontWeight: 700, color: '#dc2626', marginBottom: '0.3rem' }}>- ORIGINAL SCENARIO (Contradicted/Modifying)</div>
                          <pre style={{ fontSize: '0.75rem', color: '#991b1b', margin: 0, fontFamily: 'monospace', whiteSpace: 'pre-wrap' }}>{item.original_scenario}</pre>
                        </div>
                      )}
                      {item.suggested_change && (
                        <div style={{ background: 'rgba(16, 185, 129, 0.06)', border: '1px solid rgba(16, 185, 129, 0.2)', borderRadius: 'var(--radius-sm)', padding: '0.6rem 0.75rem' }}>
                          <div style={{ fontSize: '0.7rem', fontWeight: 700, color: '#059669', marginBottom: '0.3rem' }}>+ PROPOSED MODIFIED SCENARIO</div>
                          <pre style={{ fontSize: '0.75rem', color: '#065f46', margin: 0, fontFamily: 'monospace', whiteSpace: 'pre-wrap' }}>{item.suggested_change}</pre>
                        </div>
                      )}
                    </div>

                    {/* Action Bar */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap' }}>
                      <button
                        className="btn btn-secondary"
                        style={{ fontSize: '0.78rem', padding: '0.35rem 0.7rem' }}
                        onClick={() => handleCopyProposed(proposedText, itemId)}
                      >
                        {copyFeedback[itemId] ? '✓ Copied!' : '📋 Copy Proposed Modification'}
                      </button>

                      <button
                        className="btn btn-secondary"
                        style={{ fontSize: '0.78rem', padding: '0.35rem 0.7rem', color: 'var(--color-primary)', borderColor: 'rgba(91,138,240,0.3)' }}
                        disabled={pushingJira === itemId}
                        onClick={() => handlePushToJira(itemId, item.rationale, proposedText)}
                      >
                        {pushingJira === itemId ? <><span className="spinner" style={{ width: 12, height: 12 }} /> Pushing…</> : '📌 Push Changes to JIRA Ticket'}
                      </button>

                      <button
                        className="btn btn-secondary"
                        style={{ fontSize: '0.78rem', padding: '0.35rem 0.7rem', marginLeft: 'auto' }}
                        onClick={() => handleOpenGen(item.test_title, proposedText, item.file_raw_content || item.original_scenario || '', false)}
                      >
                        ⚡ Generate Playwright Code
                      </button>
                    </div>

                    {jiraFeedback[itemId] && (
                      <div style={{ marginTop: '0.4rem', fontSize: '0.78rem', color: jiraFeedback[itemId].includes('🎉') ? 'var(--color-emerald)' : 'var(--color-rose)' }}>
                        {jiraFeedback[itemId]}
                      </div>
                    )}
                  </div>
                )
              })}

              {/* NEEDS_EXTENSION Sub-tag items */}
              {missing_coverage.map((item, i) => {
                const itemId = `ext-${i}`
                const proposedText = Array.isArray(item.suggested_scenarios) ? item.suggested_scenarios.join('\n\n') : (item.suggested_scenarios || '')
                return (
                  <div key={itemId} style={{ padding: '1.1rem', background: 'rgba(59,130,246,0.04)', border: '1px solid rgba(59,130,246,0.2)', borderRadius: 'var(--radius-md)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.5rem', flexWrap: 'wrap' }}>
                      <span style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-primary)' }}>{item.test_title || item.file_path}</span>
                      <span className="badge badge-purple" style={{ fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Level 2: NEEDS_EXTENSION</span>
                      {item.file_path && <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>({item.file_path})</span>}
                      {confBadge(item.confidence)}
                    </div>
                    <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: '0.75rem' }}>
                      <strong>Rationale:</strong> {item.rationale}
                    </p>
                    
                    {proposedText && (
                      <div style={{ background: 'rgba(59,130,246,0.06)', border: '1px solid rgba(59,130,246,0.15)', borderRadius: 'var(--radius-sm)', padding: '0.75rem', marginBottom: '0.75rem' }}>
                        <div style={{ fontSize: '0.7rem', fontWeight: 700, color: '#2563eb', marginBottom: '0.3rem' }}>+ PROPOSED NEW SCENARIO(S) TO APPEND</div>
                        <pre style={{ fontSize: '0.75rem', color: '#1e40af', margin: 0, fontFamily: 'monospace', whiteSpace: 'pre-wrap' }}>
                          {proposedText}
                        </pre>
                      </div>
                    )}

                    {/* Action Bar */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap' }}>
                      <button
                        className="btn btn-secondary"
                        style={{ fontSize: '0.78rem', padding: '0.35rem 0.7rem' }}
                        onClick={() => handleCopyProposed(proposedText, itemId)}
                      >
                        {copyFeedback[itemId] ? '✓ Copied!' : '📋 Copy Extension Scenarios'}
                      </button>

                      <button
                        className="btn btn-secondary"
                        style={{ fontSize: '0.78rem', padding: '0.35rem 0.7rem', color: 'var(--color-primary)', borderColor: 'rgba(91,138,240,0.3)' }}
                        disabled={pushingJira === itemId}
                        onClick={() => handlePushToJira(itemId, item.rationale, proposedText)}
                      >
                        {pushingJira === itemId ? <><span className="spinner" style={{ width: 12, height: 12 }} /> Pushing…</> : '📌 Push Changes to JIRA Ticket'}
                      </button>

                      <button
                        className="btn btn-secondary"
                        style={{ fontSize: '0.78rem', padding: '0.35rem 0.7rem', marginLeft: 'auto' }}
                        onClick={() => handleOpenGen(item.test_title || 'Extension Spec', proposedText, item.file_raw_content || '', false)}
                      >
                        ⚡ Generate Playwright Code
                      </button>
                    </div>

                    {jiraFeedback[itemId] && (
                      <div style={{ marginTop: '0.4rem', fontSize: '0.78rem', color: jiraFeedback[itemId].includes('🎉') ? 'var(--color-emerald)' : 'var(--color-rose)' }}>
                        {jiraFeedback[itemId]}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )
        )}

        {/* LEVEL 1: NOT_COVERED (Story-Level Absence) */}
        {tab === 'not_covered' && (
          !isNotCovered ? (
            <p style={{ fontSize: '0.875rem', color: 'var(--color-emerald)' }}>✓ Story domain is covered by existing test cases.</p>
          ) : (() => {
            const itemId = 'not-covered-0'
            const proposedText = gaps[0]?.suggested_test || storyResult.not_covered?.proposed_file?.suggested_content || ''
            const rationaleText = gaps[0]?.scenario || storyResult.not_covered?.rationale || 'No existing test file in the repository touches this story domain.'
            const fileName = gaps[0]?.suggested_filename || storyResult.not_covered?.proposed_file?.suggested_filename || `features/${story_key.toLowerCase()}_spec.feature`
            return (
              <div style={{ padding: '1.25rem', background: 'rgba(168,85,247,0.04)', border: '1px solid rgba(168,85,247,0.2)', borderRadius: 'var(--radius-md)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.6rem' }}>
                  <span style={{ color: 'var(--color-purple)', fontSize: '1.2rem' }}>✨</span>
                  <div>
                    <h4 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                      Level 1 Verdict: NOT_COVERED (No Existing Repository Coverage)
                    </h4>
                    <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                      Proposed File: <code>{fileName}</code>
                    </span>
                  </div>
                </div>
                <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '0.75rem' }}>
                  {rationaleText}
                </p>

                {proposedText && (
                  <div style={{ background: 'var(--color-surface-2)', borderRadius: 'var(--radius-sm)', padding: '0.85rem', marginBottom: '0.85rem' }}>
                    <div style={{ fontSize: '0.7rem', fontWeight: 700, color: 'var(--color-purple)', marginBottom: '0.4rem' }}>📄 DRAFTED NEW TEST SUITE FILE CONTENT</div>
                    <pre style={{ fontSize: '0.78rem', color: 'var(--text-primary)', margin: 0, fontFamily: 'monospace', whiteSpace: 'pre-wrap', lineHeight: 1.5 }}>
                      {proposedText}
                    </pre>
                  </div>
                )}

                {/* Action Bar */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap' }}>
                  <button
                    className="btn btn-secondary"
                    style={{ fontSize: '0.78rem', padding: '0.35rem 0.7rem' }}
                    onClick={() => handleCopyProposed(proposedText, itemId)}
                  >
                    {copyFeedback[itemId] ? '✓ Copied!' : '📋 Copy Proposed Gherkin Spec'}
                  </button>

                  <button
                    className="btn btn-secondary"
                    style={{ fontSize: '0.78rem', padding: '0.35rem 0.7rem', color: 'var(--color-primary)', borderColor: 'rgba(91,138,240,0.3)' }}
                    disabled={pushingJira === itemId}
                    onClick={() => handlePushToJira(itemId, rationaleText, proposedText)}
                  >
                    {pushingJira === itemId ? <><span className="spinner" style={{ width: 12, height: 12 }} /> Pushing…</> : '📌 Push Changes to JIRA Ticket'}
                  </button>

                  <button
                    className="btn btn-primary"
                    style={{ fontSize: '0.78rem', padding: '0.4rem 0.8rem', marginLeft: 'auto' }}
                    onClick={() => handleOpenGen(fileName, rationaleText, proposedText, true)}
                  >
                    ⚡ Generate Playwright Code
                  </button>
                </div>

                {jiraFeedback[itemId] && (
                  <div style={{ marginTop: '0.4rem', fontSize: '0.78rem', color: jiraFeedback[itemId].includes('🎉') ? 'var(--color-emerald)' : 'var(--color-rose)' }}>
                    {jiraFeedback[itemId]}
                  </div>
                )}
              </div>
            )
          })()
        )}

        {/* LEVEL 1: NOT_IMPACTED */}
        {tab === 'not_impacted' && (
          unaffected.length === 0 ? (
            <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)' }}>No candidate test cases evaluated as Not Impacted.</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {unaffected.map((item, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: '0.6rem', padding: '0.75rem', background: 'rgba(16,185,129,0.03)', border: '1px solid rgba(16,185,129,0.15)', borderRadius: 'var(--radius-sm)' }}>
                  <span style={{ color: 'var(--color-emerald)', marginTop: 2, fontWeight: 'bold' }}>✓</span>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <span style={{ fontSize: '0.875rem', color: 'var(--text-primary)', fontWeight: 600 }}>{item.test_title}</span>
                      {item.file_path && <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>({item.file_path})</span>}
                      <span className="badge badge-green" style={{ fontSize: '0.68rem' }}>NOT_IMPACTED</span>
                    </div>
                    <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', margin: '0.2rem 0 0' }}>{item.rationale}</p>
                  </div>
                </div>
              ))}
            </div>
          )
        )}
      </div>

      {/* Code Generation & PR Modal (Portal at body root level) */}
      {genModal && createPortal(
        <div style={{ position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh', background: 'rgba(15, 23, 42, 0.65)', backdropFilter: 'blur(8px)', WebkitBackdropFilter: 'blur(8px)', zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '1.5rem', boxSizing: 'border-box' }}>
          <div className="glass" style={{ width: '100%', maxWidth: 850, height: '85vh', maxHeight: 800, display: 'flex', flexDirection: 'column', background: '#ffffff', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', overflow: 'hidden', boxShadow: '0 25px 50px -12px rgba(15,23,42,0.35)' }}>
            <div style={{ padding: '1.25rem 1.5rem', borderBottom: '1px solid var(--color-border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--color-surface-2)' }}>
              <div>
                <h3 style={{ margin: 0, fontSize: '1rem', display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--text-primary)' }}>🤖 Playwright Code Generator</h3>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Targeting {story_key}</span>
              </div>
              <button className="btn btn-ghost" style={{ fontSize: '1.1rem', padding: '0.2rem 0.6rem' }} onClick={() => setGenModal(null)}>✕</button>
            </div>

            <div style={{ padding: '1.5rem', overflowY: 'auto', flex: 1, display: generating ? 'flex' : 'block', flexDirection: 'column', justifyContent: 'center' }}>
              {genError && <div className="alert alert-error" style={{ marginBottom: '1rem' }}>⚠ {genError}</div>}
              {prResult && (
                <div className="alert alert-success" style={{ marginBottom: '1rem' }}>
                  🎉 <strong>Pull Request Opened!</strong> <a href={prResult.html_url} target="_blank" rel="noreferrer" style={{ color: 'var(--color-emerald)', textDecoration: 'underline' }}>PR #{prResult.number}</a>
                </div>
              )}

              {generating ? (
                <div style={{ textAlign: 'center', padding: '2rem 0', width: '100%' }}>
                  <span className="spinner" style={{ width: 36, height: 36, marginBottom: '1.2rem', borderColor: 'var(--color-primary)', borderTopColor: 'transparent' }} />
                  <p style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.3rem' }}>Generating Complete Playwright {lang === 'typescript' ? 'TypeScript' : 'JavaScript'} Test Suite…</p>
                  <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Integrating story requirements and existing test scenarios with Gemini</p>
                </div>
              ) : (
                <>
                  <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
                    <div className="input-group">
                      <label className="input-label">Target Spec File Path</label>
                      <input className="input" value={targetPath} onChange={e => setTargetPath(e.target.value)} />
                    </div>
                    <div className="input-group">
                      <label className="input-label">Language Format</label>
                      <select className="input" value={lang} onChange={e => { setLang(e.target.value); handleOpenGen(genModal.title, genModal.scenario, genModal.original, genModal.isGap, e.target.value) }}>
                        <option value="typescript">TypeScript (.spec.ts)</option>
                        <option value="javascript">JavaScript (.spec.js)</option>
                      </select>
                    </div>
                  </div>

                  <div className="input-group" style={{ marginBottom: '1rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem' }}>
                      <label className="input-label" style={{ margin: 0 }}>Generated Playwright Code (Editable)</label>
                      <button className="btn btn-ghost" style={{ fontSize: '0.78rem', padding: '0.2rem 0.5rem' }} onClick={handleCopyCode}>
                        {copied ? '✓ Copied to Clipboard!' : '📋 Copy Code'}
                      </button>
                    </div>
                    <textarea
                      className="input"
                      style={{ height: 240, fontFamily: 'JetBrains Mono, monospace', fontSize: '0.82rem', lineHeight: 1.5, whiteSpace: 'pre' }}
                      value={generatedCode}
                      onChange={e => setGeneratedCode(e.target.value)}
                    />
                  </div>

                  {/* PR Automation Options */}
                  <div style={{ background: 'var(--color-surface-2)', padding: '1rem', borderRadius: 'var(--radius-md)', marginBottom: '1rem' }}>
                    <div style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--color-secondary)', textTransform: 'uppercase', marginBottom: '0.6rem' }}>
                      🚀 GitHub PR Options
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '3fr 1fr', gap: '1rem', alignItems: 'center' }}>
                      <div className="input-group">
                        <label className="input-label">Custom PR Title (Optional)</label>
                        <input className="input" placeholder={`test(${story_key}): Automated Playwright test updates`} value={customTitle} onChange={e => setCustomTitle(e.target.value)} />
                      </div>
                      <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', marginTop: '1.2rem', fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                        <input type="checkbox" checked={isDraft} onChange={e => setIsDraft(e.target.checked)} style={{ accentColor: 'var(--color-secondary)' }} />
                        Create as Draft PR
                      </label>
                    </div>
                  </div>

                  {explanation && (
                    <div style={{ background: 'var(--color-surface-2)', padding: '0.75rem 1rem', borderRadius: 'var(--radius-sm)', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
                      <strong>AI Explanation:</strong> {explanation}
                    </div>
                  )}

                  {/* Live Playwright Execution & Controls */}
                  <div style={{ marginTop: '1.25rem', background: '#ffffff', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', padding: '1rem', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                      <span style={{ fontSize: '0.85rem', fontWeight: 700, color: '#0d9488', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                        🌐 Live Playwright Test Execution
                      </span>
                      {runStatus && (
                        <span className={`badge ${runStatus === 'passed' ? 'badge-green' : runStatus === 'running' ? 'badge-blue' : 'badge-rose'}`}>
                          {runStatus}
                        </span>
                      )}
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '0.75rem' }}>
                      <div className="input-group">
                        <label className="input-label" style={{ fontSize: '0.78rem', color: '#0d9488', fontWeight: 700 }}>
                          Target Application URL (`baseURL`) *
                        </label>
                        <input className="input" style={{ fontSize: '0.82rem', padding: '0.4rem 0.6rem', background: '#ffffff', color: 'var(--text-primary)', border: '1px solid #0d9488' }} placeholder="e.g. http://localhost:3000 or http://localhost:5173" value={targetUrl} onChange={e => setTargetUrl(e.target.value)} />
                      </div>
                      <div className="input-group">
                        <label className="input-label" style={{ fontSize: '0.78rem', color: 'var(--text-primary)', fontWeight: 600 }}>Env Vars (KEY=VALUE per line)</label>
                        <input className="input" style={{ fontSize: '0.82rem', padding: '0.4rem 0.6rem', background: '#ffffff', color: 'var(--text-primary)' }} placeholder="TEST_USER=admin&#10;API_KEY=secret" value={envInput} onChange={e => setEnvInput(e.target.value)} />
                      </div>
                    </div>

                    <div style={{ marginBottom: '0.75rem' }}>
                      <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.78rem', color: 'var(--text-primary)', cursor: 'pointer', fontWeight: 600 }}>
                        <input type="checkbox" checked={isHeaded} onChange={e => setIsHeaded(e.target.checked)} style={{ accentColor: 'var(--color-primary)' }} />
                        Launch Live Browser Window (`--headed` mode)
                      </label>
                    </div>

                    {(runningSandbox || runLogs.length > 0) && (
                      <div>
                        <div style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--text-muted)', marginBottom: '0.3rem', textTransform: 'uppercase' }}>Live Stream Execution Logs</div>
                        <pre style={{ margin: 0, maxHeight: 180, overflowY: 'auto', fontSize: '0.78rem', fontFamily: 'JetBrains Mono, monospace', color: '#0f172a', lineHeight: 1.5, whiteSpace: 'pre-wrap', background: '#f8fafc', border: '1px solid var(--color-border)', padding: '0.75rem', borderRadius: 'var(--radius-sm)' }}>
                          {runLogs.join('\n') || 'Starting Playwright live browser test runner...'}
                        </pre>
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>

            <div style={{ padding: '1.25rem 1.5rem', borderTop: '1px solid var(--color-border)', display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', background: 'var(--color-surface-2)' }}>
              <button className="btn btn-secondary" onClick={() => setGenModal(null)}>Close</button>
              <button className="btn btn-secondary" disabled={generating || runningSandbox || !generatedCode} onClick={handleRunSandbox} style={{ color: '#0d9488', borderColor: 'rgba(13,148,136,0.3)', fontWeight: 600 }}>
                {runningSandbox ? <><span className="spinner" style={{ width: 14, height: 14 }} /> Running Live…</> : '▶ Test Live in Browser'}
              </button>
              <button className="btn btn-primary" disabled={generating || creatingPR || !generatedCode} onClick={handleCreatePR}>
                {creatingPR ? <><span className="spinner" style={{ width: 14, height: 14 }} /> Creating GitHub PR…</> : '🚀 Create GitHub Pull Request'}
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
  )
}

/* ---- Main page ---- */
export default function ImpactAnalysis() {
  const [jiraConns, setJiraConns] = useState([])
  const [ghConns, setGhConns] = useState([])
  const [selectedJiraConn, setSelectedJiraConn] = useState('')
  const [projects, setProjects] = useState([])
  const [selectedProject, setSelectedProject] = useState('')
  const [stories, setStories] = useState([])
  const [selectedStories, setSelectedStories] = useState([])
  const [repos, setRepos] = useState([])
  const [selectedRepos, setSelectedRepos] = useState([])
  const [repoStats, setRepoStats] = useState({})
  const [indexingRepo, setIndexingRepo] = useState(null)
  const [selectedGhConn, setSelectedGhConn] = useState('')
  const [running, setRunning] = useState(false)
  const [results, setResults] = useState(null)
  const [error, setError] = useState('')
  const [loadingStories, setLoadingStories] = useState(false)
  const [loadingRepos, setLoadingRepos] = useState(false)

  useEffect(() => {
    api.get('/jira/connections').then(r => {
      const active = (r.data || []).filter(c => c.is_active !== false)
      setJiraConns(active)
      if (active.length > 0) setSelectedJiraConn(active[0].id)
    })
    api.get('/github/connections').then(r => {
      const active = (r.data || []).filter(c => c.is_active !== false)
      setGhConns(active)
      if (active.length > 0) setSelectedGhConn(active[active.length - 1].id)
    })
  }, [])

  const loadProjects = async () => {
    if (!selectedJiraConn) return
    const r = await api.post(`/jira/connections/${selectedJiraConn}/sync-projects`)
    setProjects(r.data)
  }

  const loadStories = async () => {
    if (!selectedProject) return
    setLoadingStories(true)
    try {
      const r = await api.post(`/jira/connections/${selectedJiraConn}/projects/${selectedProject}/sync-stories`)
      setStories(r.data)
    } catch (e) { setError(e.response?.data?.detail || 'Failed to load stories') }
    finally { setLoadingStories(false) }
  }

  const loadRepos = async () => {
    if (!selectedGhConn) return
    setLoadingRepos(true)
    try {
      const r = await api.post(`/github/connections/${selectedGhConn}/sync-repos`)
      setRepos(r.data)
      // Fetch stats for each
      const stats = {}
      await Promise.allSettled(r.data.map(async repo => {
        try {
          const s = await indexingService.getStats(repo.id)
          stats[repo.id] = s.data
        } catch { stats[repo.id] = { total: 0 } }
      }))
      setRepoStats(stats)
    } catch (e) { setError(e.response?.data?.detail || 'Failed to load repos') }
    finally { setLoadingRepos(false) }
  }

  const indexRepo = async (repo) => {
    setIndexingRepo(repo.id)
    setError('')
    try {
      await indexingService.indexRepo(selectedGhConn, repo.id)
      const s = await indexingService.getStats(repo.id)
      setRepoStats(prev => ({ ...prev, [repo.id]: s.data }))
    } catch (e) { setError(e.response?.data?.detail || 'Indexing failed') }
    finally { setIndexingRepo(null) }
  }

  const runAnalysis = async () => {
    if (!selectedStories.length) {
      setError('Please select at least one JIRA story to analyze.')
      return
    }
    if (!selectedRepos.length) {
      setError('Please select at least one GitHub repository to analyze.')
      return
    }
    setRunning(true); setError(''); setResults(null)
    try {
      const r = await impactService.runAnalysis(selectedStories, selectedRepos)
      if (r.data?.status === 'failed') {
        setError(r.data.error || 'Impact analysis run failed.')
      } else {
        setResults(r.data.results)
      }
    } catch (e) { setError(e.response?.data?.detail || 'Analysis failed') }
    finally { setRunning(false) }
  }

  const toggleStory = (id) => setSelectedStories(s => s.includes(id) ? s.filter(x => x !== id) : [...s, id])
  const toggleRepo = (id) => setSelectedRepos(s => s.includes(id) ? s.filter(x => x !== id) : [...s, id])

  return (
    <div style={{ padding: '2rem', maxWidth: '1400px', margin: '0 auto' }}>
      <div style={{ marginBottom: '2rem' }}>
        <span className="badge badge-purple" style={{ marginBottom: '0.5rem' }}>Impact Analysis</span>
        <h2 style={{ marginBottom: '0.4rem' }}>Story → Test Impact Analysis</h2>
        <p style={{ fontSize: '0.9rem' }}>Select JIRA stories and GitHub repos. AI will identify impacted test cases, unaffected ones, and coverage gaps.</p>
      </div>

      {error && <div className="alert alert-error" style={{ marginBottom: '1.5rem' }}>⚠ {error}</div>}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem', marginBottom: '1.5rem' }}>
        {/* Stories panel */}
        <div className="glass" style={{ padding: '1.5rem' }}>
          <h3 style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>1 — Select JIRA Stories</h3>
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '0.75rem' }}>
            <select className="input" style={{ flex: 1 }} value={selectedJiraConn} onChange={e => setSelectedJiraConn(e.target.value)}>
              <option value="">Connection…</option>
              {jiraConns.map(c => <option key={c.id} value={c.id}>{c.site_name}</option>)}
            </select>
            <button className="btn btn-secondary" style={{ fontSize: '0.8rem' }} onClick={loadProjects} disabled={!selectedJiraConn}>Load projects</button>
          </div>
          {projects.length > 0 && (
            <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.75rem' }}>
              <select className="input" style={{ flex: 1 }} value={selectedProject} onChange={e => setSelectedProject(e.target.value)}>
                <option value="">Project…</option>
                {projects.map(p => <option key={p.id} value={p.project_key}>{p.name}</option>)}
              </select>
              <button className="btn btn-secondary" style={{ fontSize: '0.8rem' }} onClick={loadStories} disabled={!selectedProject || loadingStories}>
                {loadingStories ? <span className="spinner" style={{ width: 12, height: 12 }} /> : 'Load'}
              </button>
            </div>
          )}
          <div style={{ maxHeight: 280, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
            {stories.map(s => (
              <label key={s.id} style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', padding: '0.5rem 0.6rem', borderRadius: 'var(--radius-sm)', background: selectedStories.includes(s.id) ? 'var(--color-primary-glow)' : 'transparent', cursor: 'pointer', border: `1px solid ${selectedStories.includes(s.id) ? 'rgba(91,138,240,0.3)' : 'transparent'}` }}>
                <input type="checkbox" checked={selectedStories.includes(s.id)} onChange={() => toggleStory(s.id)} style={{ accentColor: 'var(--color-primary)' }} />
                <span style={{ fontSize: '0.75rem', color: 'var(--color-primary)', fontWeight: 600, minWidth: 70 }}>{s.jira_issue_key}</span>
                <span style={{ fontSize: '0.82rem', color: 'var(--text-primary)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{s.summary}</span>
              </label>
            ))}
            {stories.length === 0 && <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', textAlign: 'center', padding: '1rem 0' }}>Load a project to see stories</p>}
          </div>
          <div style={{ marginTop: '0.5rem', fontSize: '0.75rem', color: 'var(--text-muted)' }}>{selectedStories.length} selected</div>
        </div>

        {/* Repos panel */}
        <div className="glass" style={{ padding: '1.5rem' }}>
          <h3 style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>2 — Select GitHub Repos</h3>
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '0.75rem' }}>
            <select className="input" style={{ flex: 1 }} value={selectedGhConn} onChange={e => setSelectedGhConn(e.target.value)}>
              <option value="">Connection…</option>
              {ghConns.map(c => <option key={c.id} value={c.id}>{c.connection_name}</option>)}
            </select>
            <button className="btn btn-secondary" style={{ fontSize: '0.8rem' }} onClick={loadRepos} disabled={!selectedGhConn || loadingRepos}>
              {loadingRepos ? <span className="spinner" style={{ width: 12, height: 12 }} /> : 'Load repos'}
            </button>
          </div>
          <div style={{ maxHeight: 280, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
            {repos.map(repo => {
              const stats = repoStats[repo.id]
              return (
                <div key={repo.id} style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', padding: '0.5rem 0.6rem', borderRadius: 'var(--radius-sm)', background: selectedRepos.includes(repo.id) ? 'rgba(139,92,246,0.08)' : 'transparent', border: `1px solid ${selectedRepos.includes(repo.id) ? 'rgba(139,92,246,0.3)' : 'transparent'}` }}>
                  <input type="checkbox" checked={selectedRepos.includes(repo.id)} onChange={() => toggleRepo(repo.id)} style={{ accentColor: 'var(--color-secondary)' }} />
                  <div style={{ flex: 1 }}>
                    <span style={{ fontSize: '0.82rem', color: 'var(--text-primary)' }}>{repo.name}</span>
                    {stats && (
                      <span style={{ fontSize: '0.7rem', color: stats.total > 0 ? 'var(--color-emerald)' : 'var(--text-muted)', marginLeft: '0.4rem' }}>
                        {stats.total > 0 ? `✓ ${stats.total} tests indexed` : '○ not indexed'}
                      </span>
                    )}
                  </div>
                  <button
                    className="btn btn-ghost"
                    style={{ fontSize: '0.72rem', padding: '0.25rem 0.5rem' }}
                    onClick={() => indexRepo(repo)}
                    disabled={indexingRepo === repo.id}
                  >
                    {indexingRepo === repo.id ? <span className="spinner" style={{ width: 10, height: 10 }} /> : '↻ Index'}
                  </button>
                </div>
              )
            })}
            {repos.length === 0 && <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', textAlign: 'center', padding: '1rem 0' }}>Load GitHub repos to index</p>}
          </div>
          <div style={{ marginTop: '0.5rem', fontSize: '0.75rem', color: 'var(--text-muted)' }}>{selectedRepos.length} selected</div>
        </div>
      </div>

      {/* Run button */}
      <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '2rem' }}>
        <button
          className="btn btn-primary"
          style={{ padding: '0.9rem 2.5rem', fontSize: '1rem' }}
          disabled={!selectedStories.length || !selectedRepos.length || running}
          onClick={runAnalysis}
        >
          {running ? (
            <><span className="spinner" style={{ width: 18, height: 18 }} /> Analysing with Gemini…</>
          ) : (
            `🔍 Run Impact Analysis (${selectedStories.length} stories × ${selectedRepos.length} repos)`
          )}
        </button>
      </div>

      {/* Results */}
      {results?.stories && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
            <h3 style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
              Analysis Results — {results.stories.length} {results.stories.length === 1 ? 'story' : 'stories'}
            </h3>
            <div style={{ display: 'flex', gap: '1rem', fontSize: '0.8rem' }}>
              <span style={{ color: 'var(--color-rose)' }}>● {results.stories.reduce((s, r) => s + (r.impacted?.length || 0), 0)} impacted</span>
              <span style={{ color: 'var(--color-amber)' }}>● {results.stories.reduce((s, r) => s + (r.missing_coverage?.length || 0), 0)} missing coverage</span>
              <span style={{ color: 'var(--color-purple)' }}>● {results.stories.reduce((s, r) => s + (r.gaps?.length || 0), 0)} new files</span>
              <span style={{ color: 'var(--color-emerald)' }}>● {results.stories.reduce((s, r) => s + (r.unaffected?.length || 0), 0)} unaffected</span>
            </div>
          </div>
          {results.stories.map(sr => (
            <StoryImpactCard
              key={sr.story_id}
              storyResult={sr}
              selectedGhConn={selectedGhConn}
              selectedRepoFullName={repos.find(r => selectedRepos.includes(r.id))?.full_name}
              selectedJiraConn={selectedJiraConn}
            />
          ))}
        </div>
      )}
    </div>
  )
}
