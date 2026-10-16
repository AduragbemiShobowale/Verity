import { useState } from 'react'
import { Link } from 'react-router-dom'
import { supabase, rpc, adminUsers } from '../../lib/supabase'
import { date, dateTime, ago } from '../../lib/format'
import { Card, PageHead, Kpi, StatusBadge, Badge, Empty, Loading, Modal, ReasonModal, useLoad, q, useAction } from '../../components/ui'

export function DispatchBoard() {
  const [picked, setPicked] = useState([])
  const [assign, setAssign] = useState(false)
  const [unassign, setUnassign] = useState(null)
  const { data, reload } = useLoad(async () => {
    const today = new Date(); today.setHours(0, 0, 0, 0)
    const [ready, board, drivers, vehicles] = await Promise.all([
      q(supabase.from('orders').select('id,order_no,status,requested_date,updated_at,customers(name),addresses(line,regions(name)),order_items(qty_picked)').in('status', ['packed', 'delivery_failed']).order('requested_date')),
      q(supabase.from('deliveries').select('*, orders(id,order_no,status,customers(name),addresses(regions(name))), driver:profiles!deliveries_driver_id_fkey(full_name), vehicles(plate)')
        .or(`current.eq.true,assigned_at.gte.${today.toISOString()}`).order('assigned_at', { ascending: false }).limit(200)),
      q(supabase.from('profiles').select('id,full_name,phone,status,drivers(active)').eq('role', 'driver').eq('status', 'active')),
      q(supabase.from('vehicles').select('*').eq('active', true).order('plate')),
    ])
    const deliveredToday = board.filter((d) => d.outcome === 'delivered' || d.outcome === 'override').filter((d) => new Date(d.delivered_at) >= today).length
    return { ready, board, drivers: drivers.filter((d) => d.drivers?.active !== false), vehicles, deliveredToday }
  })
  if (!data) return <Loading />
  const groups = {}
  data.ready.forEach((o) => { const r = o.addresses?.regions?.name || 'No region'; (groups[r] = groups[r] || []).push(o) })
  const active = data.board.filter((d) => d.current && ['assigned', 'out_for_delivery'].includes(d.orders?.status))
  const failed = data.ready.filter((o) => o.status === 'delivery_failed')
  const toggle = (id) => setPicked(picked.includes(id) ? picked.filter((x) => x !== id) : [...picked, id])
  return (
    <>
      <PageHead hero title="Dispatch board" sub="Group packed orders by area, then assign a driver and vehicle." />
      <div className="kpis">
        <Kpi label="Ready to assign" value={data.ready.length - failed.length} />
        <Kpi label="Out for delivery" value={active.filter((d) => d.orders.status === 'out_for_delivery').length} />
        <Kpi label="Delivered today" value={data.deliveredToday} />
        <Kpi label="Failed – reschedule" value={failed.length} alert={failed.length > 0} />
      </div>
      <div className="grid-main">
        <Card title="Ready for dispatch" action={<button className="btn primary" disabled={!picked.length} onClick={() => setAssign(true)}>Assign {picked.length || ''} selected</button>} pad={false}>
          {data.ready.length === 0 ? <Empty>Nothing packed yet.</Empty> : Object.entries(groups).map(([region, rows]) => (
            <div key={region}>
              <div className="row between" style={{ padding: '10px 14px', background: 'var(--surface-2)', borderBottom: '1px solid var(--line)' }}>
                <strong>{region}</strong>
                <button className="btn ghost sm" onClick={() => setPicked([...new Set([...picked, ...rows.map((r) => r.id)])])}>Select area</button>
              </div>
              <table><tbody>{rows.map((o) => (
                <tr key={o.id} className={`click ${picked.includes(o.id) ? 'selected' : ''}`} onClick={() => toggle(o.id)}>
                  <td style={{ width: 30 }}><input type="checkbox" readOnly checked={picked.includes(o.id)} aria-label={`Select ${o.order_no}`} /></td>
                  <td><strong>{o.order_no}</strong><div className="muted small">{o.customers?.name}</div></td>
                  <td className="muted small">{o.addresses?.line}</td>
                  <td>{o.status === 'delivery_failed' ? <Badge tone="bad">Reschedule</Badge> : <span className="muted small">{o.order_items.reduce((s, i) => s + i.qty_picked, 0)} units</span>}</td>
                  <td className="nowrap">{date(o.requested_date)}</td>
                </tr>
              ))}</tbody></table>
            </div>
          ))}
        </Card>
        <Card title="Delivery board" pad={false}>
          {data.board.length === 0 ? <Empty>No deliveries today.</Empty> : (
            <div className="table-wrap"><table>
              <thead><tr><th>Order</th><th>Driver</th><th>Status</th><th /></tr></thead>
              <tbody>{data.board.map((d) => (
                <tr key={d.id}>
                  <td><Link to={'/order/' + d.order_id}>{d.orders?.order_no}</Link><div className="muted small">{d.orders?.addresses?.regions?.name}</div></td>
                  <td>{d.driver?.full_name}<div className="muted small">{d.vehicles?.plate}</div></td>
                  <td>{d.current ? <StatusBadge status={d.orders?.status} /> : <Badge tone={d.outcome === 'delivered' || d.outcome === 'override' ? 'good' : d.outcome === 'failed' ? 'bad' : 'muted'}>{d.outcome}</Badge>}
                    {d.failure_reason && <div className="small muted">{d.failure_reason}</div>}
                    <div className="muted small">{ago(d.delivered_at || d.picked_up_at || d.assigned_at)}</div></td>
                  <td>{d.current && d.orders?.status === 'assigned' && <button className="btn sm" onClick={() => setUnassign(d.order_id)}>Unassign</button>}</td>
                </tr>
              ))}</tbody>
            </table></div>
          )}
        </Card>
      </div>
      {assign && <AssignModal ids={picked} drivers={data.drivers} vehicles={data.vehicles} board={active} onClose={() => setAssign(false)} onDone={() => { setAssign(false); setPicked([]); reload() }} />}
      {unassign && <ReasonModal title="Unassign delivery" label="Reason" options={['Driver unavailable', 'Vehicle problem', 'Re-planning the route', 'Customer asked for another day']}
        onClose={() => setUnassign(null)} onSubmit={async (r) => { await rpc('unassign_delivery', { p_order: unassign, p_reason: r }); reload() }} />}
    </>
  )
}

function AssignModal({ ids, drivers, vehicles, board, onClose, onDone }) {
  const [driver, setDriver] = useState('')
  const [vehicle, setVehicle] = useState('')
  const [run, busy] = useAction()
  const load = (id) => board.filter((d) => d.driver_id === id).length
  return (
    <Modal title={`Assign ${ids.length} order${ids.length > 1 ? 's' : ''}`} onClose={onClose} footer={<>
      <button className="btn" onClick={onClose}>Cancel</button>
      <button className="btn primary" disabled={!driver || busy} onClick={() => run(async () => { await rpc('assign_delivery', { p_orders: ids, p_driver: driver, p_vehicle: vehicle ? Number(vehicle) : null }); onDone() }, 'Assigned. The driver has been notified.')}>Assign</button>
    </>}>
      <label className="field">Driver
        <select value={driver} onChange={(e) => setDriver(e.target.value)}>
          <option value="">Choose…</option>
          {drivers.map((d) => <option key={d.id} value={d.id}>{d.full_name} – {load(d.id)} on the road</option>)}
        </select>
      </label>
      <label className="field">Vehicle
        <select value={vehicle} onChange={(e) => setVehicle(e.target.value)}>
          <option value="">None</option>
          {vehicles.map((v) => <option key={v.id} value={v.id}>{v.plate} – {v.description}</option>)}
        </select>
      </label>
      {drivers.length === 0 && <div className="notice warn">No active drivers. The administrator adds driver accounts.</div>}
    </Modal>
  )
}

export function Fleet() {
  const [run, busy] = useAction()
  const [f, setF] = useState({ plate: '', description: '', capacity: '' })
  const [addDriver, setAddDriver] = useState(false)
  const [secret, setSecret] = useState(null)
  const { data, reload } = useLoad(async () => {
    const [drivers, vehicles, onRoad] = await Promise.all([
      q(supabase.from('profiles').select('id,full_name,email,phone,status,last_login,must_change_password,drivers(licence_no,active)').eq('role', 'driver').order('full_name')),
      q(supabase.from('vehicles').select('*').order('plate')),
      q(supabase.from('deliveries').select('driver_id,vehicle_id,orders(status)').eq('current', true)),
    ])
    const busyIds = onRoad.filter((d) => ['assigned', 'out_for_delivery'].includes(d.orders?.status))
    return { drivers, vehicles, busyDrivers: busyIds.map((d) => d.driver_id), busyVehicles: busyIds.map((d) => d.vehicle_id) }
  })
  if (!data) return <Loading />
  const setStatus = (d, status) => run(async () => { await adminUsers({ action: 'set_status', user_id: d.id, status }); reload() },
    status === 'active' ? 'Driver reactivated.' : 'Driver deactivated. They can no longer sign in or be assigned.')
  const reset = (d) => run(async () => { const r = await adminUsers({ action: 'reset_password', user_id: d.id }); setSecret({ email: d.email, password: r.temp_password }) })
  return (
    <>
      <PageHead title="Drivers & vehicles">
        <button className="btn primary" onClick={() => setAddDriver(true)}>Add driver</button>
      </PageHead>
      <Card title="Drivers" pad={false}>
        <div className="table-wrap"><table>
          <thead><tr><th>Name</th><th>Phone</th><th>Licence</th><th>Status</th><th>Last sign-in</th><th /></tr></thead>
          <tbody>{data.drivers.map((d) => (
            <tr key={d.id}>
              <td><strong>{d.full_name}</strong><div className="muted small">{d.email}</div></td>
              <td>{d.phone}</td><td className="mono">{d.drivers?.licence_no}</td>
              <td><Badge tone={d.status === 'active' ? 'good' : 'muted'}>{d.status === 'active' ? 'Active' : 'Deactivated'}</Badge>
                {data.busyDrivers.includes(d.id) && <> <Badge tone="info">On a delivery</Badge></>}
                {d.must_change_password && <div className="muted small">Has not set own password yet</div>}</td>
              <td className="muted">{d.last_login ? ago(d.last_login) : 'never'}</td>
              <td className="row" style={{ justifyContent: 'flex-end' }}>
                <button className="btn sm" disabled={busy} onClick={() => reset(d)}>Reset password</button>
                {d.status === 'active'
                  ? <button className="btn sm danger" disabled={busy || data.busyDrivers.includes(d.id)} title={data.busyDrivers.includes(d.id) ? 'Unassign their deliveries first' : ''} onClick={() => setStatus(d, 'inactive')}>Deactivate</button>
                  : <button className="btn sm" disabled={busy} onClick={() => setStatus(d, 'active')}>Reactivate</button>}
              </td>
            </tr>
          ))}</tbody>
        </table></div>
        <div className="card-body muted small">Deactivating a driver blocks their sign-in and removes them from the assign list. Their past deliveries stay on record.</div>
      </Card>
      <Card title="Vehicles" pad={false}>
        <div className="table-wrap"><table>
          <thead><tr><th>Plate</th><th>Description</th><th className="num">Capacity (kg)</th><th>Status</th><th /></tr></thead>
          <tbody>{data.vehicles.map((v) => (
            <tr key={v.id}><td className="mono">{v.plate}</td><td>{v.description}</td><td className="num">{v.capacity}</td>
              <td><Badge tone={v.active ? 'good' : 'muted'}>{v.active ? 'In service' : 'Out of service'}</Badge>
                {data.busyVehicles.includes(v.id) && <> <Badge tone="info">On the road</Badge></>}</td>
              <td><button className="btn sm" disabled={busy} onClick={() => run(async () => { await q(supabase.from('vehicles').update({ active: !v.active }).eq('id', v.id).select()); reload() },
                v.active ? 'Taken out of service.' : 'Back in service.')}>{v.active ? 'Take out of service' : 'Return to service'}</button></td></tr>
          ))}</tbody>
        </table></div>
        <div className="card-body stack">
          <p className="muted small">"Out of service" is for a vehicle being repaired, sold or written off: it disappears from the assign list but its delivery history is kept. Nothing is deleted.</p>
          <div className="form-grid">
            <label className="field">Plate<input value={f.plate} onChange={(e) => setF({ ...f, plate: e.target.value })} /></label>
            <label className="field">Capacity (kg)<input type="number" value={f.capacity} onChange={(e) => setF({ ...f, capacity: e.target.value })} /></label>
            <label className="field full">Description<input value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} placeholder="5-tonne truck" /></label>
            <div className="full"><button className="btn primary" disabled={!f.plate.trim() || busy} onClick={() => run(async () => {
              await q(supabase.from('vehicles').insert({ plate: f.plate.trim().toUpperCase(), description: f.description, capacity: f.capacity ? Number(f.capacity) : null }).select())
              setF({ plate: '', description: '', capacity: '' }); reload()
            }, 'Vehicle added.')}>Add vehicle</button></div>
          </div>
        </div>
      </Card>
      {addDriver && <AddDriverModal onClose={() => setAddDriver(false)} onDone={(r) => { setAddDriver(false); setSecret({ email: r.email, password: r.temp_password }); reload() }} />}
      {secret && (
        <Modal title="Temporary password" onClose={() => setSecret(null)} footer={<button className="btn primary" onClick={() => setSecret(null)}>Done</button>}>
          <p>Give this to <strong>{secret.email}</strong> privately. It is shown only once. They sign in with it on their phone and must choose their own password straight away.</p>
          <div className="code-box" style={{ fontSize: 20, letterSpacing: '.08em' }}>{secret.password}</div>
        </Modal>
      )}
    </>
  )
}

function AddDriverModal({ onClose, onDone }) {
  const [f, setF] = useState({ full_name: '', email: '', phone: '', licence_no: '' })
  const [run, busy] = useAction()
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  return (
    <Modal title="Add driver" onClose={onClose} footer={<>
      <button className="btn" onClick={onClose}>Cancel</button>
      <button className="btn primary" disabled={busy || !f.full_name.trim() || !f.email.trim() || !f.phone.trim()}
        onClick={() => run(async () => onDone(await adminUsers({ action: 'create_staff', role: 'driver', ...f })))}>{busy ? 'Creating…' : 'Create driver account'}</button>
    </>}>
      <label className="field">Full name<input value={f.full_name} onChange={set('full_name')} /></label>
      <label className="field">E-mail (their username)<input type="email" value={f.email} onChange={set('email')} /></label>
      <label className="field">Phone <span className="hint">Shown to nobody but staff; used to reach the driver</span><input value={f.phone} onChange={set('phone')} inputMode="tel" /></label>
      <label className="field">Driving licence no.<input value={f.licence_no} onChange={set('licence_no')} /></label>
    </Modal>
  )
}

export function DeliveryLog() {
  const today = new Date().toISOString().slice(0, 10)
  const monthAgo = new Date(Date.now() - 30 * 86400000).toISOString().slice(0, 10)
  const [from, setFrom] = useState(monthAgo)
  const [to, setTo] = useState(today)
  const [outcome, setOutcome] = useState('all')
  const { data } = useLoad(() => rpc('delivery_log', { p_from: from || null, p_to: to || null }), [from, to])
  const rows = (data || []).filter((r) => outcome === 'all' || (outcome === 'delivered' ? ['delivered', 'override'].includes(r.outcome) : r.outcome === outcome))
  const done = (data || []).filter((r) => ['delivered', 'override'].includes(r.outcome))
  const mins = (a, b) => (a && b ? Math.round((new Date(b) - new Date(a)) / 60000) : null)
  const csv = () => {
    const head = ['Order', 'Customer', 'Region', 'Driver', 'Vehicle', 'Assigned', 'Picked up', 'Finished', 'Outcome', 'Confirmed by', 'Wrong code attempts', 'Note']
    const lines = rows.map((r) => [r.order_no, r.customer, r.region, r.driver, r.vehicle, r.assigned_at, r.picked_up_at, r.finished_at, r.outcome, r.confirmed_by, r.wrong_code_attempts ?? '', r.note ?? '']
      .map((x) => `"${String(x ?? '').replace(/"/g, '""')}"`).join(','))
    const url = URL.createObjectURL(new Blob([[head.join(','), ...lines].join('\n')], { type: 'text/csv' }))
    Object.assign(document.createElement('a'), { href: url, download: `delivery-log-${from}-to-${to}.csv` }).click()
    URL.revokeObjectURL(url)
  }
  return (
    <>
      <PageHead title="Delivery log" sub="Every finished delivery: who took it, when, and how the handover was confirmed.">
        <button className="btn" disabled={!rows.length} onClick={csv}>Download CSV</button>
      </PageHead>
      <div className="row">
        <label className="field">From<input type="date" value={from} onChange={(e) => setFrom(e.target.value)} /></label>
        <label className="field">To<input type="date" value={to} onChange={(e) => setTo(e.target.value)} /></label>
        <label className="field">Outcome
          <select value={outcome} onChange={(e) => setOutcome(e.target.value)}>
            <option value="all">All</option><option value="delivered">Delivered</option><option value="override">Ops override only</option><option value="failed">Failed</option>
          </select>
        </label>
      </div>
      <div className="kpis">
        <Kpi label="Delivered" value={done.length} />
        <Kpi label="Confirmed by customer code" value={done.filter((r) => r.outcome === 'delivered').length} />
        <Kpi label="Ops overrides" value={done.filter((r) => r.outcome === 'override').length} alert={done.some((r) => r.outcome === 'override')} />
        <Kpi label="Failed attempts" value={(data || []).filter((r) => r.outcome === 'failed').length} />
      </div>
      <Card pad={false}>
        {!data ? <Loading /> : rows.length === 0 ? <Empty>No finished deliveries in this period.</Empty> : (
          <div className="table-wrap"><table>
            <thead><tr><th>Order</th><th>Customer</th><th>Driver</th><th>Picked up</th><th>Finished</th><th>Outcome</th><th>Confirmed by</th><th className="num">Wrong codes</th></tr></thead>
            <tbody>{rows.map((r) => (
              <tr key={r.delivery_id}>
                <td><Link to={'/order/' + r.order_id}><strong>{r.order_no}</strong></Link><div className="muted small">{r.region}</div></td>
                <td>{r.customer}</td>
                <td>{r.driver}<div className="muted small">{r.vehicle}</div></td>
                <td className="nowrap">{dateTime(r.picked_up_at)}</td>
                <td className="nowrap">{dateTime(r.finished_at)}{mins(r.picked_up_at, r.finished_at) != null && <div className="muted small">{mins(r.picked_up_at, r.finished_at)} min on the road</div>}</td>
                <td><Badge tone={r.outcome === 'delivered' ? 'good' : r.outcome === 'override' ? 'warn' : 'bad'}>{r.outcome === 'override' ? 'delivered (override)' : r.outcome}</Badge>
                  {r.note && <div className="muted small" style={{ maxWidth: 260 }}>{r.note}</div>}</td>
                <td>{r.confirmed_by}</td>
                <td className="num">{r.wrong_code_attempts ?? '—'}</td>
              </tr>
            ))}</tbody>
          </table></div>
        )}
      </Card>
    </>
  )
}

export { dateTime }
