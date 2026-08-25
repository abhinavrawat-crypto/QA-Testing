import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

export default function Login() {
  const { login } = useAuth()
  const navigate   = useNavigate()
  const [form, setForm]   = useState({ email: '', password: '' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handle = (e) => setForm(f => ({ ...f, [e.target.name]: e.target.value }))

  const submit = async (e) => {
    e.preventDefault()
    setError(''); setLoading(true)
    try {
      await login(form.email, form.password)
      navigate('/dashboard')
    } catch (err) {
      setError(err.response?.data?.detail || 'Login failed')
    } finally { setLoading(false) }
  }

  return (
    <div style={{ minHeight:'calc(100vh - 64px)', display:'flex', alignItems:'center', justifyContent:'center', padding:'2rem' }}>
      <div className="glass animate-fade-up" style={{ width:'100%', maxWidth:440, padding:'2.5rem' }}>
        <div style={{ textAlign:'center', marginBottom:'2rem' }}>
          <div style={{ fontSize:'2.5rem', marginBottom:'0.5rem', color: 'var(--color-primary)' }}>✦</div>
          <h2 style={{ marginBottom:'0.4rem', color: 'var(--text-primary)' }}>Welcome back</h2>
          <p style={{ fontSize:'0.875rem', color: 'var(--text-secondary)' }}>Sign in to your QualityAI account</p>
        </div>

        {error && <div className="alert alert-error" style={{ marginBottom:'1.25rem' }}>⚠ {error}</div>}

        <form onSubmit={submit} style={{ display:'flex', flexDirection:'column', gap:'1.1rem' }}>
          <div className="input-group">
            <label className="input-label">Email</label>
            <input className="input" type="email" name="email" placeholder="you@company.com" value={form.email} onChange={handle} required />
          </div>
          <div className="input-group">
            <label className="input-label">Password</label>
            <input className="input" type="password" name="password" placeholder="••••••••" value={form.password} onChange={handle} required />
          </div>
          <button className="btn btn-primary" type="submit" disabled={loading} style={{ width:'100%', justifyContent:'center', marginTop:'0.25rem', padding:'0.8rem' }}>
            {loading ? <><span className="spinner" style={{ width:16, height:16 }} /> Signing in…</> : 'Sign in →'}
          </button>
        </form>

        <div className="divider" style={{ margin:'1.5rem 0' }}>or</div>
        <p style={{ textAlign:'center', fontSize:'0.875rem' }}>
          New here? <Link to="/register">Create an account</Link>
        </p>
      </div>
    </div>
  )
}
