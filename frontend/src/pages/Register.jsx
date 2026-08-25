import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

export default function Register() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ name: '', email: '', password: '', confirm: '' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handle = (e) => setForm(f => ({ ...f, [e.target.name]: e.target.value }))

  const submit = async (e) => {
    e.preventDefault()
    if (form.password !== form.confirm) { setError('Passwords do not match'); return }
    if (form.password.length < 8) { setError('Password must be at least 8 characters'); return }
    setError(''); setLoading(true)
    try {
      await register(form.name, form.email, form.password)
      navigate('/onboarding')
    } catch (err) {
      setError(err.response?.data?.detail || 'Registration failed')
    } finally { setLoading(false) }
  }

  return (
    <div style={{ minHeight:'calc(100vh - 64px)', display:'flex', alignItems:'center', justifyContent:'center', padding:'2rem' }}>
      <div className="glass animate-fade-up" style={{ width:'100%', maxWidth:460, padding:'2.5rem' }}>
        <div style={{ textAlign:'center', marginBottom:'2rem' }}>
          <div style={{ fontSize:'2.5rem', marginBottom:'0.5rem', color: 'var(--color-primary)' }}>✦</div>
          <h2 style={{ marginBottom:'0.4rem', color: 'var(--text-primary)' }}>Get started</h2>
          <p style={{ fontSize:'0.875rem', color: 'var(--text-secondary)' }}>Create your QualityAI account</p>
        </div>

        {error && <div className="alert alert-error" style={{ marginBottom:'1.25rem' }}>⚠ {error}</div>}

        <form onSubmit={submit} style={{ display:'flex', flexDirection:'column', gap:'1rem' }}>
          <div className="input-group">
            <label className="input-label">Full name</label>
            <input className="input" name="name" placeholder="Jane Smith" value={form.name} onChange={handle} required minLength={2} />
          </div>
          <div className="input-group">
            <label className="input-label">Work email</label>
            <input className="input" type="email" name="email" placeholder="jane@company.com" value={form.email} onChange={handle} required />
          </div>
          <div className="input-group">
            <label className="input-label">Password</label>
            <input className="input" type="password" name="password" placeholder="Min. 8 characters" value={form.password} onChange={handle} required />
          </div>
          <div className="input-group">
            <label className="input-label">Confirm password</label>
            <input className="input" type="password" name="confirm" placeholder="Re-enter password" value={form.confirm} onChange={handle} required />
          </div>
          <button className="btn btn-primary" type="submit" disabled={loading} style={{ width:'100%', justifyContent:'center', marginTop:'0.25rem', padding:'0.8rem' }}>
            {loading ? <><span className="spinner" style={{ width:16, height:16 }} /> Creating account…</> : 'Create account →'}
          </button>
        </form>

        <div className="divider" style={{ margin:'1.5rem 0' }}>or</div>
        <p style={{ textAlign:'center', fontSize:'0.875rem' }}>
          Already have an account? <Link to="/login">Sign in</Link>
        </p>
      </div>
    </div>
  )
}
