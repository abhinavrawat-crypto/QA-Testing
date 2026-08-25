import { Link, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

export default function Navbar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => { logout(); navigate('/') }

  return (
    <nav className="navbar">
      <div className="navbar-inner">
        <Link to="/" className="navbar-logo">
          <div style={{ background: 'linear-gradient(135deg, #2563eb 0%, #0d9488 100%)', width: 34, height: 34, borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.1rem', fontWeight: 900, color: '#ffffff', boxShadow: '0 4px 12px rgba(37, 99, 235, 0.25)' }}>
            Q
          </div>
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <span style={{ fontWeight: 800, letterSpacing: '-0.3px', fontSize: '1.15rem', color: '#0f172a', lineHeight: 1.1 }}>QualityAI</span>
            <span style={{ fontSize: '0.62rem', color: '#0d9488', letterSpacing: '1px', textTransform: 'uppercase', fontWeight: 700 }}>Enterprise Quality</span>
          </div>
        </Link>

        <div className="navbar-nav">
          {user ? (
            <>
              <NavLink to="/dashboard" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>Home</NavLink>
              <NavLink to="/feature-a" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>Story Audit</NavLink>
              <NavLink to="/feature-b" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>Impact Analysis</NavLink>
              <NavLink to="/feature-c" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>Story Discovery</NavLink>
              <NavLink to="/settings" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>Settings</NavLink>
              <button className="btn btn-ghost" onClick={handleLogout} style={{ fontSize: '0.85rem' }}>Sign out</button>
              <div style={{ width: 34, height: 34, borderRadius: '50%', background: 'linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.85rem', fontWeight: 700, color: '#fff', boxShadow: '0 2px 8px rgba(37,99,235,0.2)' }}>
                {user.name?.[0]?.toUpperCase()}
              </div>
            </>
          ) : (
            <>
              <Link to="/login" className="nav-link" style={{ fontSize: '0.9rem', color: '#475569' }}>Sign in</Link>
              <Link to="/register" className="btn btn-primary" style={{ padding: '0.6rem 1.4rem', fontSize: '0.875rem' }}>
                Get Started Free →
              </Link>
            </>
          )}
        </div>
      </div>
    </nav>
  )
}
