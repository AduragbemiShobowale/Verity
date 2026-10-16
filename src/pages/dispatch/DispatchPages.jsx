import { useState } from 'react'
import { Link } from 'react-router-dom'
import { supabase, rpc } from '../../lib/supabase'
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
      <PageHead title="Dispatch board" sub="Group packed orders by area, then assign a driver and vehicle." />
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
  const { data, reload } = useLoad(async () => {
    const [drivers, vehicles] = await Promise.all([
      q(supabase.from('profiles').select('id,full_name,email,phone,status,drivers(licence_no,active)').eq('role', 'driver').order('full_name')),
      q(supabase.from('vehicles').select('*').order('plate')),
    ])
    return { drivers, vehicles }
  })
  if (!data) return <Loading />
  return (
    <>
      <PageHead title="Drivers & vehicles" />
      <div className="grid-2">
        <Card title="Drivers" pad={false}>
          <div className="table-wrap"><table>
            <thead><tr><th>Name</th><th>Phone</th><th>Licence</th><th>Status</th></tr></thead>
            <tbody>{data.drivers.map((d) => (
              <tr key={d.id}><td>{d.full_name}<div className="muted small">{d.email}</div></td><td>{d.phone}</td><td className="mono">{d.drivers?.licence_no}</td>
                <td><Badge tone={d.status === 'active' ? 'good' : 'muted'}>{d.status}</Badge></td></tr>
            ))}</tbody>
          </table></div>
          <div className="card-body muted small">Driver accounts are created by the administrator.</div>
        </Card>
        <Card title="Vehicles" pad={false}>
          <div className="table-wrap"><table>
            <thead><tr><th>Plate</th><th>Description</th><th className="num">Capacity (kg)</th><th /></tr></thead>
            <tbody>{data.vehicles.map((v) => (
              <tr key={v.id}><td className="mono">{v.plate}</td><td>{v.description}</td><td className="num">{v.capacity}</td>
                <td><button className="btn sm" disabled={busy} onClick={() => run(async () => { await q(supabase.from('vehicles').update({ active: !v.active }).eq('id', v.id).select()); reload() })}>{v.active ? 'Retire' : 'Reactivate'}</button></td></tr>
            ))}</tbody>
          </table></div>
          <div className="card-body form-grid">
            <label className="field">Plate<input value={f.plate} onChange={(e) => setF({ ...f, plate: e.target.value })} /></label>
            <label className="field">Capacity (kg)<input type="number" value={f.capacity} onChange={(e) => setF({ ...f, capacity: e.target.value })} /></label>
            <label className="field full">Description<input value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} /></label>
            <div className="full"><button className="btn primary" disabled={!f.plate.trim() || busy} onClick={() => run(async () => {
              await q(supabase.from('vehicles').insert({ plate: f.plate.trim().toUpperCase(), description: f.description, capacity: f.capacity ? Number(f.capacity) : null }).select())
              setF({ plate: '', description: '', capacity: '' }); reload()
            }, 'Vehicle added.')}>Add vehicle</button></div>
          </div>
        </Card>
      </div>
    </>
  )
}

export { dateTime }
