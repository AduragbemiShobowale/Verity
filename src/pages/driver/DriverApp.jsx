import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import toast from 'react-hot-toast'
import { rpc } from '../../lib/supabase'
import { useAuth } from '../../context/AuthContext'
import { date, dateTime } from '../../lib/format'
import { StatusBadge, Badge, Kpi, Empty, Loading, ReasonModal, useLoad, useAction } from '../../components/ui'

// Phone-first pages inside the shared layout (sidebar on desktop, menu
// button on a phone). The driver sees only their own assigned orders, the
// contact, address and items. Never prices, invoice, payment status or the code.

function Head({ title, back, sub }) {
  return (
    <div className="stack" style={{ gap: 4 }}>
      {back && <Link to={back} className="small">← Back</Link>}
      <h1>{title}</h1>
      {sub && <p className="muted">{sub}</p>}
    </div>
  )
}

export function DriverDashboard() {
  const { profile } = useAuth()
  const now = useLoad(() => rpc('driver_deliveries'))
  const past = useLoad(() => rpc('driver_history'))
  const today = new Date().toDateString()
  const waiting = now.data?.filter((d) => d.status === 'assigned') || []
  const onRoad = now.data?.filter((d) => d.status === 'out_for_delivery') || []
  const doneToday = (past.data || []).filter((h) => ['delivered', 'override'].includes(h.outcome) && new Date(h.at).toDateString() === today)
  const failed = (past.data || []).filter((h) => h.outcome === 'failed')
  const next = onRoad[0] || waiting[0]
  return (
    <div className="driver-page">
      <Head title={`Hello ${profile?.full_name?.split(' ')[0] || ''}`} sub={new Date().toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long' })} />
      <div className="kpis">
        <Kpi label="To collect at warehouse" value={now.data ? waiting.length : null} to="/deliveries" />
        <Kpi label="On the road" value={now.data ? onRoad.length : null} to="/deliveries" />
        <Kpi label="Delivered today" value={past.data ? doneToday.length : null} to="/history" />
        <Kpi label="Failed (14 days)" value={past.data ? failed.length : null} to="/history" alert={failed.length > 0} />
      </div>
      {next ? (
        <Link to={'/delivery/' + next.order_id} className="card card-pad stack" style={{ color: 'inherit', textDecoration: 'none' }}>
          <div className="row between"><h2>Next: {next.order_no}</h2><StatusBadge status={next.status} /></div>
          <div><strong>{next.customer}</strong><div className="muted">{next.address} · {next.region}</div></div>
          <span className="btn primary block">{next.status === 'assigned' ? 'Open and confirm pickup' : 'Open and enter the code'}</span>
        </Link>
      ) : now.data && <div className="card"><Empty>No deliveries assigned right now. You will get a notification when Dispatch assigns one.</Empty></div>}
    </div>
  )
}

const useDeliveries = () => useLoad(() => rpc('driver_deliveries'))

export function DriverList() {
  const { profile } = useAuth()
  const { data, reload } = useDeliveries()
  const [run, busy] = useAction()
  const nav = useNavigate()
  const waiting = data?.filter((d) => d.status === 'assigned') || []
  const onRoad = data?.filter((d) => d.status === 'out_for_delivery') || []
  return (
    <div className="driver-page">
      <Head title="My deliveries" sub={data ? `${data.length} deliver${data.length === 1 ? 'y' : 'ies'} assigned to you.` : ''} />
        {!data ? <Loading /> : data.length === 0 ? <div className="card"><Empty>No deliveries assigned. Pull to refresh or wait for a notification.</Empty></div> : null}
        {waiting.length > 0 && (
          <div className="card card-pad stack">
            <div className="row between"><h2>At the warehouse</h2><Badge tone="info">{waiting.length} to collect</Badge></div>
            {waiting.map((d) => (
              <div key={d.order_id} className="row between" style={{ borderTop: '1px solid var(--line)', paddingTop: 10 }}>
                <div onClick={() => nav('/delivery/' + d.order_id)} style={{ cursor: 'pointer' }}><strong>{d.order_no}</strong><div className="muted small">{d.customer} · {d.region}</div></div>
                <button className="btn primary" disabled={busy} onClick={() => run(async () => { await rpc('confirm_pickup', { p_order: d.order_id }); reload() }, 'Pickup confirmed.')}>Confirm pickup</button>
              </div>
            ))}
            {waiting.length > 1 && <button className="btn block" disabled={busy} onClick={() => run(async () => { for (const d of waiting) await rpc('confirm_pickup', { p_order: d.order_id }); reload() }, 'All picked up.')}>Confirm pickup for all {waiting.length}</button>}
          </div>
        )}
        {onRoad.map((d) => (
          <Link key={d.order_id} to={'/delivery/' + d.order_id} className="card card-pad stack" style={{ color: 'inherit', textDecoration: 'none' }}>
            <div className="row between"><strong style={{ fontSize: 16 }}>{d.order_no}</strong><StatusBadge status={d.status} /></div>
            <div><strong>{d.customer}</strong><div className="muted">{d.address}</div></div>
            <div className="muted small">{d.items.length} item lines · {d.items.reduce((s, i) => s + i.qty, 0)} units{d.vehicle ? ` · ${d.vehicle}` : ''}</div>
          </Link>
        ))}
        <Link to="/history" className="btn block">Recent deliveries</Link>
    </div>
  )
}

export function DriverDetail() {
  const { id } = useParams()
  const nav = useNavigate()
  const { data, reload } = useDeliveries()
  const [code, setCode] = useState('')
  const [msg, setMsg] = useState(null)
  const [fail, setFail] = useState(false)
  const [run, busy] = useAction()
  if (!data) return <div className="driver-page"><Head title="Delivery" back="/deliveries" /><Loading /></div>
  const d = data.find((x) => x.order_id === id)
  if (!d) return <div className="driver-page"><Head title="Delivery" back="/deliveries" /><div className="card"><Empty>This delivery is no longer assigned to you.</Empty></div></div>
  const maps = 'https://www.google.com/maps/search/?api=1&query=' + encodeURIComponent(`${d.address}, ${d.region}, Nigeria`)
  const submit = () => run(async () => {
    const r = await rpc('confirm_delivery', { p_order: d.order_id, p_code: code })
    if (r.ok) {
      toast.success('Delivered. Thank you!')
      nav('/')
    } else {
      setMsg(r)
      setCode('')
      reload()
    }
  })
  return (
    <div className="driver-page">
      <Head title={d.order_no} back="/deliveries" />
        <div className="card card-pad stack">
          <StatusBadge status={d.status} />
          <div><strong style={{ fontSize: 17 }}>{d.customer}</strong><div>{d.contact}</div></div>
          <a className="btn block lg" href={'tel:' + d.phone}>Call {d.phone}</a>
          <div><div className="muted small">Address</div><div>{d.address}</div><div className="muted small">{d.region}</div></div>
          {d.instructions && <div className="notice info">{d.instructions}</div>}
          {d.notes && <div className="notice info">{d.notes}</div>}
          <a className="btn block" href={maps} target="_blank" rel="noopener noreferrer">Open in maps</a>
        </div>
        <div className="card card-pad stack">
          <h2>Packages</h2>
          {d.items.map((i, n) => <div key={n} className="row between"><span>{i.name}</span><strong>{i.qty} {i.unit}</strong></div>)}
        </div>
        {d.status === 'assigned' && (
          <button className="btn primary lg block" disabled={busy} onClick={() => run(async () => { await rpc('confirm_pickup', { p_order: d.order_id }); reload() }, 'Pickup confirmed.')}>Confirm pickup</button>
        )}
        {d.status === 'out_for_delivery' && (
          <div className="card card-pad stack">
            <h2>Confirm delivery</h2>
            <p className="muted">Ask the customer for the 6-digit code on their dashboard.</p>
            {d.code_locked ? (
              <div className="notice bad">The code is locked after too many wrong attempts. The Ops Desk has been alerted and will re-issue it or confirm by phone.</div>
            ) : (
              <>
                <input className="code-input" inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))} aria-label="Delivery code" />
                <div className="muted small">{d.attempts_left} attempt{d.attempts_left === 1 ? '' : 's'} left</div>
                {msg && !msg.ok && <div className="notice bad">{msg.message}</div>}
                <button className="btn primary lg block" disabled={code.length !== 6 || busy} onClick={submit}>Confirm delivery</button>
              </>
            )}
            <button className="btn danger block" onClick={() => setFail(true)}>Delivery failed</button>
          </div>
        )}
      {fail && <ReasonModal title="Delivery failed" label="What happened?" danger confirm="Report"
        options={['Customer not available', 'Wrong or incomplete address', 'Customer refused the goods', 'Site closed / no access', 'Vehicle breakdown']}
        onClose={() => setFail(false)} onSubmit={async (r) => { await rpc('report_delivery_failed', { p_order: d.order_id, p_reason: r }); nav('/') }} />}
    </div>
  )
}

export function DriverHistory() {
  const { data } = useLoad(() => rpc('driver_history'))
  return (
    <div className="driver-page">
      <Head title="Recent deliveries" sub="Your last 14 days." />
        {!data ? <Loading /> : data.length === 0 ? <div className="card"><Empty>Nothing in the last 14 days.</Empty></div> : data.map((h, i) => (
          <div key={i} className="card card-pad row between">
            <div><strong>{h.order_no}</strong><div className="muted small">{h.customer} · {dateTime(h.at)}</div>{h.failure_reason && <div className="small">{h.failure_reason}</div>}</div>
            <Badge tone={h.outcome === 'delivered' || h.outcome === 'override' ? 'good' : h.outcome === 'failed' ? 'bad' : 'muted'}>{h.outcome || 'reassigned'}</Badge>
          </div>
        ))}
    </div>
  )
}

export { date }
