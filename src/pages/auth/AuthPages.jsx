import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import { supabase, rpc } from '../../lib/supabase'
import { useAuth } from '../../context/AuthContext'
import { BrandMark } from '../../components/Layout'
import AuthScene from '../../components/AuthScene'

export function AuthFrame({ children, wide }) {
  return (
    <div className="auth">
      <div className="auth-art">
        <AuthScene />
        <Link to="/" className="brand" style={{ color: '#fff', textDecoration: 'none' }}><BrandMark /> Verity</Link>
        <div className="stack-lg">
          <h1>Orders that arrive right the first time.</h1>
          <ul>
            <li>Pick products from the live catalogue, or upload the spreadsheet you already use.</li>
            <li>Every order is checked instantly: stock, prices, quantities, duplicates, address.</li>
            <li>Pay by transfer, track every step, and hand the driver your delivery code.</li>
          </ul>
        </div>
        <small style={{ color: '#9fbab4' }}>Intelligent order processing for logistics teams</small>
      </div>
      <div className="auth-form">
        <div className={`auth-card ${wide ? 'wide' : ''}`}>
          <div className="auth-mini"><AuthScene compact /></div>
          {children}
        </div>
      </div>
    </div>
  )
}


export function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)
  const submit = async (e) => {
    e.preventDefault()
    setBusy(true); setErr(null)
    const { error } = await supabase.auth.signInWithPassword({ email: email.trim(), password })
    setBusy(false)
    if (error) return setErr(error.message === 'Invalid login credentials' ? 'Wrong e-mail or password.' : error.message)
    rpc('touch_login').catch(() => {})
  }
  return (
    <AuthFrame>
      <div>
        <h1>Sign in</h1>
        <p className="muted">Customers and staff use the same sign-in.</p>
      </div>
      <form className="stack" onSubmit={submit}>
        <label className="field">E-mail<input type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required /></label>
        <label className="field">Password<input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required /></label>
        {err && <div className="notice bad">{err}</div>}
        <button className="btn primary lg" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
      </form>
      <div className="row between">
        <Link to="/forgot">Forgot password?</Link>
        <span>New business? <Link to="/register">Register</Link></span>
      </div>
    </AuthFrame>
  )
}

export function Register() {
  const [f, setF] = useState({ full_name: '', email: '', password: '', confirm: '' })
  const [busy, setBusy] = useState(false)
  const [sent, setSent] = useState(false)
  const [err, setErr] = useState(null)
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const submit = async (e) => {
    e.preventDefault()
    if (f.password.length < 8) return setErr('Use at least 8 characters for the password.')
    if (f.password !== f.confirm) return setErr('The passwords do not match.')
    setBusy(true); setErr(null)
    const { data, error } = await supabase.auth.signUp({
      email: f.email.trim(), password: f.password,
      options: { data: { full_name: f.full_name.trim() }, emailRedirectTo: window.location.origin },
    })
    setBusy(false)
    if (error) return setErr(error.message)
    if (!data.session) setSent(true)
  }
  if (sent) {
    return (
      <AuthFrame>
        <h1>Check your e-mail</h1>
        <p>We sent a link to <strong>{f.email}</strong>. Open it to verify your address, then sign in to complete your company details.</p>
        <Link className="btn" to="/login">Back to sign in</Link>
      </AuthFrame>
    )
  }
  return (
    <AuthFrame>
      <div>
        <h1>Register your business</h1>
        <p className="muted">Step 1 of 2: create your sign-in. Next you will add company details and documents for review.</p>
      </div>
      <form className="stack" onSubmit={submit}>
        <label className="field">Your name<input value={f.full_name} onChange={set('full_name')} required /></label>
        <label className="field">Work e-mail <span className="hint">This becomes your username.</span><input type="email" value={f.email} onChange={set('email')} required /></label>
        <label className="field">Password<input type="password" autoComplete="new-password" value={f.password} onChange={set('password')} required /></label>
        <label className="field">Confirm password<input type="password" autoComplete="new-password" value={f.confirm} onChange={set('confirm')} required /></label>
        {err && <div className="notice bad">{err}</div>}
        <button className="btn primary lg" disabled={busy}>{busy ? 'Creating…' : 'Create account'}</button>
      </form>
      <p>Already registered? <Link to="/login">Sign in</Link></p>
    </AuthFrame>
  )
}

export function Forgot() {
  const [email, setEmail] = useState('')
  const [done, setDone] = useState(false)
  const submit = async (e) => {
    e.preventDefault()
    const { error } = await supabase.auth.resetPasswordForEmail(email.trim(), { redirectTo: window.location.origin + '/reset' })
    if (error) return toast.error(error.message)
    setDone(true)
  }
  return (
    <AuthFrame>
      <h1>Reset password</h1>
      {done ? (
        <p>If an account exists for {email}, a reset link is on its way.</p>
      ) : (
        <form className="stack" onSubmit={submit}>
          <label className="field">E-mail<input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required /></label>
          <button className="btn primary">Send reset link</button>
        </form>
      )}
      <Link to="/login">Back to sign in</Link>
    </AuthFrame>
  )
}

// Used for a recovery link and for the forced first-login change.
export function SetPassword({ forced }) {
  const { setRecovery, refresh, signOut } = useAuth()
  const [p1, setP1] = useState('')
  const [p2, setP2] = useState('')
  const [busy, setBusy] = useState(false)
  const nav = useNavigate()
  const submit = async (e) => {
    e.preventDefault()
    if (p1.length < 8) return toast.error('Use at least 8 characters.')
    if (p1 !== p2) return toast.error('The passwords do not match.')
    setBusy(true)
    const { error } = await supabase.auth.updateUser({ password: p1 })
    if (error) { setBusy(false); return toast.error(error.message) }
    await rpc('password_changed').catch(() => {})
    toast.success('Password updated.')
    setRecovery(false)
    await refresh()
    nav('/')
  }
  return (
    <AuthFrame>
      <div>
        <h1>{forced ? 'Choose your own password' : 'Set a new password'}</h1>
        {forced && <p className="muted">Your account was created with a temporary password. Replace it before you continue.</p>}
      </div>
      <form className="stack" onSubmit={submit}>
        <label className="field">New password<input type="password" autoComplete="new-password" value={p1} onChange={(e) => setP1(e.target.value)} required /></label>
        <label className="field">Confirm<input type="password" autoComplete="new-password" value={p2} onChange={(e) => setP2(e.target.value)} required /></label>
        <button className="btn primary lg" disabled={busy}>Save password</button>
      </form>
      <button className="btn ghost" onClick={signOut}>Sign out</button>
    </AuthFrame>
  )
}

export function VerifyEmail() {
  const { user, signOut } = useAuth()
  const resend = async () => {
    const { error } = await supabase.auth.resend({ type: 'signup', email: user.email, options: { emailRedirectTo: window.location.origin } })
    error ? toast.error(error.message) : toast.success('Sent again.')
  }
  return (
    <AuthFrame>
      <h1>Verify your e-mail</h1>
      <p>Open the link we sent to <strong>{user?.email}</strong>. Our team only reviews applications from verified addresses.</p>
      <div className="row"><button className="btn primary" onClick={resend}>Resend link</button><button className="btn" onClick={() => window.location.reload()}>I have verified</button></div>
      <button className="btn ghost" onClick={signOut}>Sign out</button>
    </AuthFrame>
  )
}
