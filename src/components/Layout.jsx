import { Component, useState, useEffect } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useLive } from './Live'
import { supabase } from '../lib/supabase'
import { ROLE_LABEL, ago } from '../lib/format'
import { Modal } from './ui'

const count = (table, build) => async () => {
  const { count: c } = await build(supabase.from(table).select('id', { count: 'exact', head: true }))
  return c || 0
}

// Open items needing a person, from attention_summary(). Each kind holds order ids.
const attention = (...kinds) => async () => {
  const { data, error } = await supabase.rpc('attention_summary')
  if (error) throw error
  return new Set(kinds.flatMap((k) => data[k] || [])).size
}

export const MENUS = {
  customer: [
    { to: '/', label: 'Dashboard', end: true },
    { to: '/new-order', label: 'New order' },
    { to: '/orders', label: 'My orders' },
    { to: '/invoices', label: 'Invoices & pay', count: count('orders', (q) => q.in('status', ['awaiting_payment', 'payment_rejected'])) },
    { to: '/codes', label: 'Delivery codes', count: count('orders', (q) => q.eq('status', 'out_for_delivery')) },
    { to: '/catalogue', label: 'Catalogue' },
    { to: '/profile', label: 'Profile & addresses' },
  ],
  ops: [
    { to: '/', label: 'Dashboard', end: true },
    { to: '/ops/approvals', label: 'Approval queue', count: count('orders', (q) => q.eq('status', 'pending_approval')) },
    { to: '/ops/shortages', label: 'Shortage cases', count: count('orders', (q) => q.eq('status', 'shortage_hold')) },
    { to: '/ops/orders', label: 'All orders' },
    { to: '/ops/refunds', label: 'Refund requests' },
    { to: '/ops/alerts', label: 'Alerts', count: attention('code_problems', 'escalations', 'cancel_requests', 'failed') },
    { to: '/ops/customers', label: 'Customers' },
    { to: '/reports', label: 'Reports' },
  ],
  finance: [
    { to: '/', label: 'Dashboard', end: true },
    { to: '/finance/payments', label: 'Payments to verify', count: count('payments', (q) => q.eq('status', 'pending')) },
    { to: '/finance/refunds', label: 'Refunds', count: count('refunds', (q) => q.eq('status', 'requested')) },
    { to: '/finance/invoices', label: 'Invoices' },
  ],
  warehouse: [
    { to: '/', label: 'Dashboard', end: true },
    { to: '/warehouse/pick', label: 'Pick list', count: count('orders', (q) => q.in('status', ['paid', 'picking'])) },
    { to: '/warehouse/stock', label: 'Stock levels' },
    { to: '/warehouse/new-product', label: 'New product' },
    { to: '/warehouse/stock-in', label: 'Stock in' },
    { to: '/warehouse/adjust', label: 'Adjustments' },
    { to: '/warehouse/movements', label: 'Stock history' },
  ],
  driver: [
    { to: '/', label: 'Dashboard', end: true },
    { to: '/deliveries', label: 'My deliveries', count: async () => (await supabase.rpc('driver_deliveries')).data?.length || 0 },
    { to: '/history', label: 'Recent deliveries' },
  ],
  dispatch: [
    { to: '/', label: 'Dispatch board', end: true, count: attention('to_assign', 'failed', 'code_problems') },
    { to: '/dispatch/log', label: 'Delivery log' },
    { to: '/dispatch/fleet', label: 'Drivers & vehicles' },
  ],
  admin: [
    { to: '/', label: 'Dashboard', end: true },
    { to: '/admin/registrations', label: 'Registrations', count: count('customers', (q) => q.eq('status', 'awaiting_review')) },
    { to: '/admin/users', label: 'Users & roles' },
    { to: '/admin/customers', label: 'Customers' },
    { to: '/admin/catalogue', label: 'Catalogue & prices', count: count('products', (q) => q.eq('active', false).eq('price', 0)) },
    { to: '/admin/regions', label: 'Regions & fees' },
    { to: '/admin/rules', label: 'Rules & settings' },
    { to: '/admin/audit', label: 'Audit log' },
    { to: '/reports', label: 'Performance' },
    { to: '/ops/orders', label: 'All orders' },
  ],
}

export function Bell() {
  const { items, unread, markRead, markAll } = useLive()
  const [open, setOpen] = useState(false)
  const nav = useNavigate()
  const loc = useLocation()
  useEffect(() => setOpen(false), [loc.pathname])
  return (
    <>
      <button className="icon-btn" aria-label={`Notifications, ${unread} unread`} onClick={() => setOpen((o) => !o)}>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" /><path d="M13.7 21a2 2 0 0 1-3.4 0" /></svg>
        {unread > 0 && <span className="dot">{unread > 9 ? '9+' : unread}</span>}
      </button>
      {open && (
        <div className="bell-pop">
          <div className="row between" style={{ padding: '12px 14px', borderBottom: '1px solid var(--line)' }}>
            <h3>Notifications</h3>
            {unread > 0 && <button className="btn ghost sm" onClick={markAll}>Mark all read</button>}
          </div>
          {items.length === 0 && <div className="empty">Nothing yet.</div>}
          {items.map((n) => (
            <div key={n.id} className={`notif ${n.read_at ? '' : 'unread'}`} onClick={() => { markRead([n.id]); if (n.link) nav(n.link); setOpen(false) }}>
              <div className="row between"><strong>{n.title}</strong><span className="muted small">{ago(n.created_at)}</span></div>
              {n.body && <div className="muted small">{n.body}</div>}
            </div>
          ))}
        </div>
      )}
    </>
  )
}

function NavCount({ fn }) {
  const { tick } = useLive()
  const loc = useLocation()
  const [n, setN] = useState(0)
  useEffect(() => { fn().then(setN).catch(() => {}) }, [tick, loc.pathname, loc.search]) // eslint-disable-line react-hooks/exhaustive-deps
  return n > 0 ? <span className="count">{n}</span> : null
}

// Keeps a crash in one page from blanking the whole screen. Resets when the route changes.
class PageErrorBoundary extends Component {
  state = { error: null }
  static getDerivedStateFromError(error) { return { error } }
  componentDidUpdate(prev) { if (prev.path !== this.props.path && this.state.error) this.setState({ error: null }) }
  render() {
    if (!this.state.error) return this.props.children
    return (
      <div className="notice warn">
        <strong>This page could not be shown.</strong> Try reloading. If it keeps happening, tell the administrator.
        <div className="muted small mono">{String(this.state.error.message || this.state.error)}</div>
      </div>
    )
  }
}

export const BrandMark = () => (
  <span className="brand-mark">
    <svg width="16" height="16" viewBox="0 0 32 32"><path d="M7 8l9 17 9-17" fill="none" stroke="#f2c14e" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" /></svg>
  </span>
)

export default function Layout() {
  const { role, profile, customer, signOut } = useAuth()
  const [open, setOpen] = useState(false)
  const [confirmOut, setConfirmOut] = useState(false)
  const loc = useLocation()
  useEffect(() => setOpen(false), [loc.pathname])
  const menu = MENUS[role] || []
  return (
    <div className="shell" data-role={role}>
      <aside className={`side ${open ? 'open' : ''}`}>
        <NavLink to="/" className="brand" style={{ textDecoration: 'none' }} aria-label="Verity home"><BrandMark /> Verity</NavLink>
        <div className="role-chip">{ROLE_LABEL[role]}</div>
        <nav className="nav">
          {menu.map((m) => (
            <NavLink key={m.to} to={m.to} end={m.end}>
              <span>{m.label}</span>
              {m.count && <NavCount fn={m.count} />}
            </NavLink>
          ))}
        </nav>
        <div className="side-foot">
          <div>
            <strong>{profile?.full_name || profile?.email}</strong>
            <div className="muted small">{customer?.name || profile?.email}</div>
          </div>
          <NavLink to="/account" className="small">Account & password</NavLink>
          <button className="btn sm" onClick={() => setConfirmOut(true)}>Sign out</button>
        </div>
      </aside>
      <div className="main">
        <header className="top">
          <button className="icon-btn menu-btn" aria-label="Menu" onClick={() => setOpen((o) => !o)}>☰</button>
          <div className="spacer" />
          <Bell />
        </header>
        <main className="page">
          <PageErrorBoundary path={loc.pathname}><Outlet /></PageErrorBoundary>
        </main>
      </div>
      {open && <div className="side-scrim" onClick={() => setOpen(false)} />}
      {confirmOut && (
        <Modal title="Sign out?" onClose={() => setConfirmOut(false)} footer={<>
          <button className="btn" onClick={() => setConfirmOut(false)}>Stay signed in</button>
          <button className="btn primary" onClick={signOut}>Sign out</button>
        </>}>
          <p>You will need your e-mail and password to sign in again.</p>
        </Modal>
      )}
    </div>
  )
}
