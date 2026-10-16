import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { supabase, rpc } from '../../lib/supabase'
import { money, date, dateTime, ago, STATUS, ACTIVE_STATUSES } from '../../lib/format'
import { Card, PageHead, Kpi, StatusBadge, Badge, Empty, Loading, ReasonModal, ValidationReport, useLoad, q, countOf, useAction } from '../../components/ui'
import { OrderTableStaff } from '../shared/StaffOrder'

const head = () => ({ count: 'exact', head: true })

async function stuckOrders() {
  const { data: s } = await supabase.from('settings').select('value').eq('key', 'stuck_order_hours').single()
  const hrs = Number(s?.value || 24)
  const since = new Date(Date.now() - hrs * 3600000).toISOString()
  const rows = await q(supabase.from('orders').select('id,order_no,status,updated_at,total,requested_date,customers(name)')
    .in('status', ACTIVE_STATUSES.filter((x) => !['validation_failed', 'rejected'].includes(x))).lt('updated_at', since).order('updated_at').limit(50))
  return { rows, hrs }
}

export function OpsDashboard() {
  const nav = useNavigate()
  const { data } = useLoad(async () => {
    const today = new Date(); today.setHours(0, 0, 0, 0)
    const [pending, shortage, stuck, approvedToday, queue, alerts] = await Promise.all([
      countOf(supabase.from('orders').select('id', head()).eq('status', 'pending_approval')),
      countOf(supabase.from('orders').select('id', head()).eq('status', 'shortage_hold')),
      stuckOrders(),
      countOf(supabase.from('approvals').select('id', head()).eq('decision', 'approved').gte('decided_at', today.toISOString())),
      q(supabase.from('orders').select('id,order_no,total,submitted_at,validation_outcome,customers(name)').eq('status', 'pending_approval').order('submitted_at').limit(8)),
      q(supabase.from('notifications').select('*').in('event', ['shortage', 'low_stock', 'code_locked', 'refund_requested', 'payment_escalation', 'delivery_failed', 'cancel_requested', 'restock_overdue', 'code_expired']).order('created_at', { ascending: false }).limit(10)),
    ])
    const byStatus = await q(supabase.from('orders').select('status').in('status', ACTIVE_STATUSES))
    const tally = {}
    byStatus.forEach((o) => { tally[o.status] = (tally[o.status] || 0) + 1 })
    return { pending, shortage, stuck, approvedToday, queue, alerts, tally }
  })
  return (
    <>
      <PageHead title="Operations & Approval Desk" sub="Approvals, shortages and every open order." />
      <div className="kpis">
        <Kpi label="Pending approval" value={data?.pending} to="/ops/approvals" alert={data?.pending > 0} />
        <Kpi label="Shortage cases" value={data?.shortage} to="/ops/shortages" alert={data?.shortage > 0} />
        <Kpi label={`Stuck over ${data?.stuck.hrs ?? 24} h`} value={data?.stuck.rows.length} to="/ops/alerts" alert={data?.stuck.rows.length > 0} />
        <Kpi label="Approved today" value={data?.approvedToday} />
      </div>
      <div className="grid-main">
        <Card title="Approval queue (oldest first)" pad={false} action={<Link to="/ops/approvals">Open queue</Link>}>
          {!data ? <Loading /> : data.queue.length === 0 ? <Empty>Queue is clear.</Empty> : (
            <div className="table-wrap"><table>
              <thead><tr><th>Order</th><th>Customer</th><th>Waiting</th><th>Checks</th><th className="num">Total</th></tr></thead>
              <tbody>{data.queue.map((o) => (
                <tr key={o.id} className="click" onClick={() => nav('/ops/approvals?o=' + o.id)}>
                  <td><strong>{o.order_no}</strong></td><td>{o.customers?.name}</td><td>{ago(o.submitted_at)}</td>
                  <td>{o.validation_outcome === 'warn' ? <Badge tone="warn">Warnings</Badge> : <Badge tone="good">Clean</Badge>}</td>
                  <td className="num">{money(o.total)}</td>
                </tr>
              ))}</tbody>
            </table></div>
          )}
        </Card>
        <div className="stack-lg">
          <Card title="Order tracker">
            {!data ? <Loading /> : (
              <div className="stack">
                {ACTIVE_STATUSES.filter((s) => data.tally[s]).map((s) => (
                  <Link key={s} to={'/ops/orders'} className="row between" style={{ color: 'inherit' }}>
                    <StatusBadge status={s} /><strong>{data.tally[s]}</strong>
                  </Link>
                ))}
                {Object.keys(data.tally).length === 0 && <Empty>No open orders.</Empty>}
              </div>
            )}
          </Card>
          <Card title="Recent alerts" action={<Link to="/ops/alerts">All alerts</Link>}>
            {!data ? <Loading /> : data.alerts.length === 0 ? <Empty>No alerts.</Empty> : (
              <div className="stack">{data.alerts.map((n) => (
                <Link key={n.id} to={n.order_id ? '/order/' + n.order_id : n.link || '#'} style={{ color: 'inherit' }}>
                  <strong>{n.title}</strong> <span className="muted small">{ago(n.created_at)}</span>
                  {n.body && <div className="muted small">{n.body}</div>}
                </Link>
              ))}</div>
            )}
          </Card>
        </div>
      </div>
    </>
  )
}

export function Approvals() {
  const params = new URLSearchParams(window.location.search)
  const [sel, setSel] = useState(params.get('o'))
  const [modal, setModal] = useState(null)
  const [comment, setComment] = useState('')
  const [run, busy] = useAction()
  const { data, reload } = useLoad(() => q(supabase.from('orders')
    .select('id,order_no,total,submitted_at,validation_outcome,requested_date,customer_id,customers(name,payment_terms,created_at)')
    .eq('status', 'pending_approval').order('submitted_at')))
  const current = data?.find((o) => o.id === sel) || data?.[0]
  const detail = useLoad(async () => {
    if (!current) return null
    const [items, vr, hist] = await Promise.all([
      q(supabase.from('order_items').select('*').eq('order_id', current.id).gt('qty_ordered', 0)),
      q(supabase.from('validation_results').select('*').eq('order_id', current.id).eq('current', true).order('id')),
      q(supabase.from('orders').select('id,status,total').eq('customer_id', current.customer_id).neq('status', 'draft').neq('id', current.id)),
    ])
    return { items, vr, hist }
  }, [current?.id])
  const d = detail.data
  return (
    <>
      <PageHead title="Approval queue" sub="Oldest first. Approving reserves stock, issues the invoice and starts the payment window." />
      {!data ? <Loading /> : data.length === 0 ? <Card><Empty>Nothing waiting for approval.</Empty></Card> : (
        <div className="grid-main" style={{ gridTemplateColumns: 'minmax(0,1fr) minmax(0,1.6fr)' }}>
          <Card pad={false}>
            <div className="table-wrap"><table>
              <tbody>{data.map((o) => (
                <tr key={o.id} className={`click ${current?.id === o.id ? 'selected' : ''}`} onClick={() => setSel(o.id)}>
                  <td><strong>{o.order_no}</strong><div className="muted small">{o.customers?.name}</div></td>
                  <td>{o.validation_outcome === 'warn' ? <Badge tone="warn">Warnings</Badge> : <Badge tone="good">Clean</Badge>}<div className="muted small">{ago(o.submitted_at)}</div></td>
                  <td className="num">{money(o.total)}</td>
                </tr>
              ))}</tbody>
            </table></div>
          </Card>
          {current && (
            <Card title={`${current.order_no} · ${current.customers?.name}`} action={<Link to={'/order/' + current.id}>Full view</Link>}>
              {!d ? <Loading /> : (
                <div className="stack-lg">
                  <div className="row">
                    <Badge tone="info">{d.hist.length} previous orders</Badge>
                    <Badge tone="good">{d.hist.filter((h) => h.status === 'delivered').length} delivered</Badge>
                    {d.hist.length === 0 && <Badge tone="warn">New customer</Badge>}
                    <Badge>{current.customers?.payment_terms}</Badge>
                    <span className="muted small">Delivery {date(current.requested_date)}</span>
                  </div>
                  <ValidationReport results={d.vr} />
                  <div className="table-wrap"><table>
                    <thead><tr><th>Product</th><th className="num">Qty</th><th className="num">Unit</th><th className="num">Total</th></tr></thead>
                    <tbody>{d.items.map((i) => <tr key={i.id}><td>{i.product_name}<div className="muted small">{i.product_sku}</div></td><td className="num">{i.qty_ordered}</td><td className="num">{money(i.unit_price)}</td><td className="num">{money(i.qty_ordered * i.unit_price)}</td></tr>)}</tbody>
                  </table></div>
                  <div className="row between"><span className="muted">Invoice total</span><strong style={{ fontSize: 18 }}>{money(current.total)}</strong></div>
                  <label className="field">Comment (optional)<input value={comment} onChange={(e) => setComment(e.target.value)} /></label>
                  <div className="row">
                    <button className="btn primary lg" disabled={busy} onClick={() => run(async () => { await rpc('approve_order', { p_order: current.id, p_comment: comment }); setComment(''); setSel(null); reload() }, 'Approved.')}>Approve</button>
                    <button className="btn danger lg" onClick={() => setModal('reject')}>Reject</button>
                  </div>
                </div>
              )}
            </Card>
          )}
        </div>
      )}
      {modal === 'reject' && current && <ReasonModal title={`Reject ${current.order_no}`} label="Reason (the customer sees this)" danger confirm="Reject" onClose={() => setModal(null)}
        options={['Delivery date cannot be met', 'Quantity looks wrong – please confirm', 'Duplicate of another order', 'Customer account under review', 'Other: see order notes']}
        onSubmit={async (r) => { await rpc('reject_order', { p_order: current.id, p_reason: r }); setSel(null); reload() }} />}
    </>
  )
}

export function Shortages() {
  const nav = useNavigate()
  const { data } = useLoad(() => q(supabase.from('orders').select('id,order_no,status,total,updated_at,requested_date,shortage_choice,shortage_at,cancel_requested_reason,customers(name)').eq('status', 'shortage_hold').order('shortage_at')))
  return (
    <>
      <PageHead title="Shortage cases" sub="The customer chooses in the portal; record their choice here if they call instead." />
      <Card pad={false}>
        {!data ? <Loading /> : data.length === 0 ? <Empty>No shortages.</Empty> : (
          <div className="table-wrap"><table>
            <thead><tr><th>Order</th><th>Customer</th><th>Since</th><th>Customer choice</th><th className="num">Total</th></tr></thead>
            <tbody>{data.map((o) => (
              <tr key={o.id} className="click" onClick={() => nav('/order/' + o.id)}>
                <td><strong>{o.order_no}</strong></td><td>{o.customers?.name}</td><td>{ago(o.shortage_at)}</td>
                <td>{o.shortage_choice ? <Badge tone="info">{o.shortage_choice.replace('_', ' ')}</Badge> : <Badge tone="warn">Waiting for customer</Badge>}</td>
                <td className="num">{money(o.total)}</td>
              </tr>
            ))}</tbody>
          </table></div>
        )}
      </Card>
    </>
  )
}

export function OpsRefunds() {
  const { data } = useLoad(() => q(supabase.from('refunds').select('*, orders(order_no), customers(name)').order('requested_at', { ascending: false }).limit(200)))
  return (
    <>
      <PageHead title="Refund requests" sub="Raised automatically for shortages and paid cancellations, or by you from an order. Finance pays them." />
      <Card pad={false}>
        {!data ? <Loading /> : data.length === 0 ? <Empty>No refunds.</Empty> : (
          <div className="table-wrap"><table>
            <thead><tr><th>Order</th><th>Customer</th><th>Reason</th><th>Requested</th><th>Status</th><th className="num">Amount</th></tr></thead>
            <tbody>{data.map((r) => (
              <tr key={r.id}><td><Link to={'/order/' + r.order_id}>{r.orders?.order_no}</Link></td><td>{r.customers?.name}</td><td>{r.reason}</td>
                <td>{dateTime(r.requested_at)}</td><td><Badge tone={r.status === 'paid' ? 'good' : 'warn'}>{r.status}{r.credit_note_no ? ' · ' + r.credit_note_no : ''}</Badge></td><td className="num">{money(r.amount)}</td></tr>
            ))}</tbody>
          </table></div>
        )}
      </Card>
    </>
  )
}

export function Alerts() {
  const nav = useNavigate()
  const { data } = useLoad(async () => {
    const [stuck, cancelReq, failed, escalations, locked, low] = await Promise.all([
      stuckOrders(),
      q(supabase.from('orders').select('id,order_no,status,updated_at,cancel_requested_reason,customers(name)').not('cancel_requested_reason', 'is', null)),
      q(supabase.from('orders').select('id,order_no,status,updated_at,customers(name)').eq('status', 'delivery_failed')),
      q(supabase.from('notifications').select('order_id').eq('event', 'payment_escalation').order('created_at', { ascending: false }).limit(50)),
      q(supabase.from('notifications').select('order_id,created_at').in('event', ['code_locked', 'code_expired']).order('created_at', { ascending: false }).limit(50)),
      q(supabase.from('products').select('id,sku,name,on_hand,reserved,reorder_level').eq('active', true)),
    ])
    const ids = [...new Set([...escalations, ...locked].map((n) => n.order_id).filter(Boolean))]
    const open = ids.length ? await q(supabase.from('orders').select('id,order_no,status,updated_at,customers(name)').in('id', ids).in('status', ['payment_rejected', 'out_for_delivery'])) : []
    return { stuck, cancelReq, failed, open, low: low.filter((p) => p.on_hand - p.reserved <= p.reorder_level) }
  })
  if (!data) return <Loading />
  const open = (o) => nav('/order/' + o.id)
  return (
    <>
      <PageHead title="Alerts" sub="Everything that needs a person." />
      <Card title={`Cancellation requests (${data.cancelReq.length})`} pad={false}><OrderTableStaff rows={data.cancelReq} onOpen={open} /></Card>
      <Card title={`Locked or expired delivery codes, payment escalations (${data.open.length})`} pad={false}><OrderTableStaff rows={data.open} onOpen={open} /></Card>
      <Card title={`Failed deliveries (${data.failed.length})`} pad={false}><OrderTableStaff rows={data.failed} onOpen={open} /></Card>
      <Card title={`Stuck in one status over ${data.stuck.hrs} h (${data.stuck.rows.length})`} pad={false}><OrderTableStaff rows={data.stuck.rows} onOpen={open} /></Card>
      <Card title={`Low stock (${data.low.length})`} pad={false}>
        {data.low.length === 0 ? <Empty>All products above reorder level.</Empty> : (
          <div className="table-wrap"><table>
            <thead><tr><th>Product</th><th className="num">Available</th><th className="num">Reorder level</th></tr></thead>
            <tbody>{data.low.map((p) => <tr key={p.id}><td>{p.name} <span className="muted mono">{p.sku}</span></td><td className="num">{Math.max(p.on_hand - p.reserved, 0)}</td><td className="num">{p.reorder_level}</td></tr>)}</tbody>
          </table></div>
        )}
      </Card>
    </>
  )
}

export function OpsCustomers() {
  const { data } = useLoad(async () => {
    const [cust, orders] = await Promise.all([
      q(supabase.from('customers').select('*').order('name')),
      q(supabase.from('orders').select('customer_id,status,total').neq('status', 'draft')),
    ])
    return cust.map((c) => {
      const mine = orders.filter((o) => o.customer_id === c.id)
      return { ...c, n: mine.length, delivered: mine.filter((o) => o.status === 'delivered').length, value: mine.filter((o) => o.status === 'delivered').reduce((s, o) => s + Number(o.total), 0) }
    })
  })
  return (
    <>
      <PageHead title="Customers" />
      <Card pad={false}>
        {!data ? <Loading /> : (
          <div className="table-wrap"><table>
            <thead><tr><th>Company</th><th>Contact</th><th>Status</th><th>Terms</th><th className="num">Orders</th><th className="num">Delivered value</th></tr></thead>
            <tbody>{data.map((c) => (
              <tr key={c.id}><td><strong>{c.name}</strong><div className="muted small">{c.reg_no}</div></td><td>{c.contact_name}<div className="muted small">{c.phone}</div></td>
                <td><Badge tone={c.status === 'active' ? 'good' : 'warn'}>{c.status.replace('_', ' ')}</Badge></td><td>{c.payment_terms}</td>
                <td className="num">{c.n}</td><td className="num">{money(c.value)}</td></tr>
            ))}</tbody>
          </table></div>
        )}
      </Card>
    </>
  )
}

export { STATUS }
