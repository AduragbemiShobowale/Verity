import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { supabase, rpc } from '../../lib/supabase'
import { date, dateTime, ago } from '../../lib/format'
import { Card, PageHead, Kpi, StatusBadge, Badge, Empty, Loading, Modal, useLoad, q, countOf, useAction } from '../../components/ui'

const head = () => ({ count: 'exact', head: true })

export function WarehouseDashboard() {
  const nav = useNavigate()
  const { data } = useLoad(async () => {
    const today = new Date(); today.setHours(0, 0, 0, 0)
    const [ready, picking, products, packedToday, list] = await Promise.all([
      countOf(supabase.from('orders').select('id', head()).eq('status', 'paid')),
      countOf(supabase.from('orders').select('id', head()).eq('status', 'picking')),
      q(supabase.from('products').select('*').eq('active', true).order('name')),
      countOf(supabase.from('order_events').select('id', head()).eq('to_status', 'packed').gte('at', today.toISOString())),
      q(supabase.from('orders').select('id,order_no,status,requested_date,customers(name),order_items(qty_ordered)').in('status', ['paid', 'picking']).order('requested_date').limit(10)),
    ])
    return { ready, picking, products, packedToday, list, low: products.filter((p) => p.on_hand - p.reserved <= p.reorder_level) }
  })
  return (
    <>
      <PageHead title="Warehouse" sub="Only paid orders reach the pick list." />
      <div className="kpis">
        <Kpi label="Ready to pick" value={data?.ready} to="/warehouse/pick" />
        <Kpi label="In picking" value={data?.picking} to="/warehouse/pick" />
        <Kpi label="Low-stock items" value={data?.low.length} to="/warehouse/stock" alert={data?.low.length > 0} />
        <Kpi label="Packed today" value={data?.packedToday} />
      </div>
      <div className="grid-main">
        <Card title="Pick list" pad={false} action={<Link to="/warehouse/pick">Open</Link>}>
          <PickTable rows={data?.list} onOpen={(o) => nav('/warehouse/pick/' + o.id)} />
        </Card>
        <Card title="Stock vs reorder level">
          {!data ? <Loading /> : <StockBars products={data.products} />}
        </Card>
      </div>
    </>
  )
}

function StockBars({ products }) {
  const max = Math.max(...products.map((p) => Math.max(p.on_hand - p.reserved, p.reorder_level * 2)), 1)
  return (
    <div className="stack">
      {products.map((p) => {
        const avail = Math.max(p.on_hand - p.reserved, 0)
        const low = avail <= p.reorder_level
        return (
          <div key={p.id}>
            <div className="row between small"><span>{p.name}</span><span className={low ? '' : 'muted'} style={low ? { color: 'var(--bad)', fontWeight: 600 } : {}}>{avail} / reorder {p.reorder_level}</span></div>
            <div className={`bar ${low ? 'low' : ''}`}><span style={{ width: `${Math.min(100, (avail / max) * 100)}%` }} /></div>
          </div>
        )
      })}
    </div>
  )
}

function PickTable({ rows, onOpen }) {
  if (!rows) return <Loading />
  if (!rows.length) return <Empty>Nothing to pick.</Empty>
  return (
    <div className="table-wrap"><table>
      <thead><tr><th>Order</th><th>Customer</th><th>Delivery date</th><th className="num">Lines</th><th>Status</th></tr></thead>
      <tbody>{rows.map((o) => (
        <tr key={o.id} className="click" onClick={() => onOpen(o)}>
          <td><strong>{o.order_no}</strong></td><td>{o.customers?.name}</td><td>{date(o.requested_date)}</td>
          <td className="num">{o.order_items?.filter((i) => i.qty_ordered > 0).length}</td>
          <td><StatusBadge status={o.status} />{o.shortage_choice === 'wait_restock' && <div className="small muted">waiting for restock</div>}</td>
        </tr>
      ))}</tbody>
    </table></div>
  )
}

export function PickList() {
  const nav = useNavigate()
  const { data } = useLoad(async () => {
    const [list, waiting] = await Promise.all([
      q(supabase.from('orders').select('id,order_no,status,requested_date,customers(name),order_items(qty_ordered)').in('status', ['paid', 'picking']).order('requested_date')),
      q(supabase.from('orders').select('id,order_no,status,requested_date,shortage_choice,customers(name),order_items(qty_ordered)').eq('status', 'shortage_hold').eq('shortage_choice', 'wait_restock')),
    ])
    return { list, waiting }
  })
  return (
    <>
      <PageHead title="Pick list" sub="Paid orders by delivery date." />
      <Card pad={false}><PickTable rows={data?.list} onOpen={(o) => nav('/warehouse/pick/' + o.id)} /></Card>
      <Card title="Waiting for restock" pad={false}><PickTable rows={data?.waiting} onOpen={(o) => nav('/warehouse/pick/' + o.id)} /></Card>
    </>
  )
}

export function Picking() {
  const { id } = useParams()
  const nav = useNavigate()
  const [found, setFound] = useState({})
  const [run, busy] = useAction()
  const { data, reload } = useLoad(() => q(supabase.from('orders').select('*, customers(name), order_items(*)').eq('id', id).single()), [id])
  if (!data) return <Loading />
  const o = data
  const items = o.order_items.filter((i) => i.qty_ordered > 0)
  const open = items.filter((i) => i.qty_picked < i.qty_ordered)
  const start = () => run(async () => { await rpc('start_picking', { p_order: o.id }); reload() }, 'Picking started.')
  const submit = () => run(async () => {
    const lines = open.map((i) => ({ item_id: i.id, qty_found: Number(found[i.id] ?? i.qty_ordered - i.qty_picked) }))
    const r = await rpc('record_pick', { p_order: o.id, p_lines: lines })
    nav('/warehouse/pick')
    return r
  }, (r) => (r === 'packed' ? 'Packed. Sent to dispatch.' : 'Shortage recorded. Ops Desk and customer notified.'))
  const short = open.some((i) => Number(found[i.id] ?? i.qty_ordered - i.qty_picked) < i.qty_ordered - i.qty_picked)
  return (
    <>
      <PageHead title={`Pick ${o.order_no}`} sub={`${o.customers?.name} · deliver ${date(o.requested_date)}`}><StatusBadge status={o.status} /></PageHead>
      {o.notes && <div className="notice info"><strong>Order notes</strong>{o.notes}</div>}
      {(o.status === 'paid' || (o.status === 'shortage_hold' && o.shortage_choice === 'wait_restock')) && (
        <Card><div className="row between"><span>{o.status === 'paid' ? 'Start picking to lock this order to you.' : 'Stock has been received? Resume picking the remaining items.'}</span><button className="btn primary" disabled={busy} onClick={start}>{o.status === 'paid' ? 'Start picking' : 'Resume picking'}</button></div></Card>
      )}
      <Card title="Lines" pad={false}>
        <div className="table-wrap"><table>
          <thead><tr><th>Product</th><th className="num">Ordered</th><th className="num">Already picked</th><th style={{ width: 140 }}>Found now</th></tr></thead>
          <tbody>{items.map((i) => {
            const remaining = i.qty_ordered - i.qty_picked
            return (
              <tr key={i.id}>
                <td><strong>{i.product_name}</strong><div className="muted mono">{i.product_sku}</div></td>
                <td className="num">{i.qty_ordered} {i.unit}</td>
                <td className="num">{i.qty_picked}</td>
                <td>{remaining === 0 ? <Badge tone="good">Done</Badge> : (
                  <input type="number" min="0" max={remaining} disabled={o.status !== 'picking'} value={found[i.id] ?? remaining}
                    onChange={(e) => setFound({ ...found, [i.id]: e.target.value })} aria-label={`Found for ${i.product_name}`} />
                )}</td>
              </tr>
            )
          })}</tbody>
        </table></div>
      </Card>
      {o.status === 'picking' && (
        <div className="row">
          {short && <div className="notice warn">Less than ordered: the order goes to Shortage Hold and the customer chooses what to do.</div>}
          <button className="btn primary lg" disabled={busy} onClick={submit}>{short ? 'Record shortage' : 'Mark packed'}</button>
        </div>
      )}
    </>
  )
}

export function StockLevels() {
  const { data } = useLoad(() => q(supabase.from('products').select('*').order('name')))
  return (
    <>
      <PageHead title="Stock levels" sub="Available = on hand − reserved for approved orders." />
      <Card pad={false}>
        {!data ? <Loading /> : (
          <div className="table-wrap"><table>
            <thead><tr><th>Product</th><th className="num">On hand</th><th className="num">Reserved</th><th className="num">Available</th><th className="num">Reorder level</th><th /></tr></thead>
            <tbody>{data.map((p) => {
              const avail = p.on_hand - p.reserved
              return (
                <tr key={p.id}><td><strong>{p.name}</strong><div className="muted mono">{p.sku}{!p.active && ' · inactive'}</div></td>
                  <td className="num">{p.on_hand}</td><td className="num">{p.reserved}</td>
                  <td className="num"><strong style={avail <= p.reorder_level ? { color: 'var(--bad)' } : {}}>{avail}</strong></td>
                  <td className="num">{p.reorder_level}</td>
                  <td>{avail <= p.reorder_level && <Badge tone="bad">Reorder</Badge>}</td></tr>
              )
            })}</tbody>
          </table></div>
        )}
      </Card>
    </>
  )
}

function StockForm({ mode }) {
  const [f, setF] = useState({ product: '', qty: '', reference: '', reason: '' })
  const [run, busy] = useAction()
  const { data, reload } = useLoad(() => q(supabase.from('products').select('id,sku,name,on_hand,reserved').order('name')))
  const cur = data?.find((p) => p.id === f.product)
  const go = () => run(async () => {
    if (mode === 'in') await rpc('stock_in', { p_product: f.product, p_qty: Number(f.qty), p_reference: f.reference, p_reason: f.reason })
    else await rpc('adjust_stock', { p_product: f.product, p_delta: Number(f.qty), p_reason: f.reason })
    setF({ product: f.product, qty: '', reference: '', reason: '' })
    reload()
  }, mode === 'in' ? 'Stock recorded.' : 'Adjustment recorded.')
  return (
    <>
      <PageHead title={mode === 'in' ? 'Stock in' : 'Adjustments'} sub={mode === 'in' ? 'Record goods received with the delivery note or PO number.' : 'Correct counts after a stock take, damage or loss. Every adjustment needs a reason and is audited.'} />
      <Card>
        <div className="form-grid">
          <label className="field full">Product
            <select value={f.product} onChange={(e) => setF({ ...f, product: e.target.value })}>
              <option value="">Choose…</option>
              {data?.map((p) => <option key={p.id} value={p.id}>{p.name} ({p.sku}) – on hand {p.on_hand}</option>)}
            </select>
          </label>
          <label className="field">{mode === 'in' ? 'Quantity received' : 'Change (+ or −)'}<input type="number" value={f.qty} onChange={(e) => setF({ ...f, qty: e.target.value })} /></label>
          {mode === 'in' && <label className="field">Reference<input value={f.reference} onChange={(e) => setF({ ...f, reference: e.target.value })} placeholder="GRN-0042" /></label>}
          <label className={`field ${mode === 'in' ? 'full' : ''}`}>Reason {mode === 'in' && <span className="hint">optional</span>}
            {mode === 'in' ? <input value={f.reason} onChange={(e) => setF({ ...f, reason: e.target.value })} placeholder="Supplier delivery" />
              : <select value={f.reason} onChange={(e) => setF({ ...f, reason: e.target.value })}>
                <option value="">Choose…</option>
                {['Stock take correction', 'Damaged goods', 'Lost / missing', 'Found during count', 'Returned by customer'].map((r) => <option key={r}>{r}</option>)}
              </select>}
          </label>
          {cur && mode === 'adjust' && f.qty && <div className="notice info full">On hand goes from {cur.on_hand} to {cur.on_hand + Number(f.qty)}.{cur.on_hand + Number(f.qty) < cur.reserved && ' This is below what is reserved for approved orders, so some will be short at picking.'}</div>}
          <div className="full"><button className="btn primary" disabled={busy || !f.product || !f.qty || (mode === 'adjust' && !f.reason) || (mode === 'in' && !f.reference)} onClick={go}>Save</button></div>
        </div>
      </Card>
    </>
  )
}
export const StockIn = () => <StockForm mode="in" />
export const Adjustments = () => <StockForm mode="adjust" />

export function Movements() {
  const { data } = useLoad(() => q(supabase.from('stock_movements').select('*, products(sku,name), profiles(full_name)').order('at', { ascending: false }).limit(200)))
  const tone = { in: 'good', reserve: 'info', release: 'muted', pick: 'accent', adjust: 'warn' }
  return (
    <>
      <PageHead title="Stock history" sub="Every change to stock, newest first." />
      <Card pad={false}>
        {!data ? <Loading /> : (
          <div className="table-wrap"><table>
            <thead><tr><th>When</th><th>Product</th><th>Type</th><th className="num">Qty</th><th>Reason / reference</th><th>By</th></tr></thead>
            <tbody>{data.map((m) => (
              <tr key={m.id}><td className="nowrap">{dateTime(m.at)}</td><td>{m.products?.name}</td><td><Badge tone={tone[m.type]}>{m.type}</Badge></td>
                <td className="num">{m.qty}</td><td>{m.reason}{m.reference && <span className="muted"> · {m.reference}</span>}</td><td className="muted">{m.profiles?.full_name || 'system'}</td></tr>
            ))}</tbody>
          </table></div>
        )}
      </Card>
    </>
  )
}

export { ago, Modal }
