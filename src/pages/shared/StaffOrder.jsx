import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { supabase, rpc, signedUrl } from '../../lib/supabase'
import { useAuth } from '../../context/AuthContext'
import { money, date, dateTime, STATUS, ACTIVE_STATUSES } from '../../lib/format'
import { Card, PageHead, StatusBadge, Badge, Empty, Loading, ReasonModal, Timeline, ValidationReport, useLoad, q, useAction } from '../../components/ui'

export function OrderTableStaff({ rows, onOpen, showCustomer = true }) {
  if (!rows) return <Loading />
  if (!rows.length) return <Empty>No orders.</Empty>
  return (
    <div className="table-wrap"><table>
      <thead><tr><th>Order</th>{showCustomer && <th>Customer</th>}<th>Status</th><th>Updated</th><th>Delivery</th><th className="num">Total</th></tr></thead>
      <tbody>{rows.map((o) => (
        <tr key={o.id} className="click" onClick={() => onOpen(o)}>
          <td><strong>{o.order_no}</strong>{o.cancel_requested_reason && <div><Badge tone="bad">Cancel requested</Badge></div>}</td>
          {showCustomer && <td>{o.customers?.name}</td>}
          <td><StatusBadge status={o.status} /></td>
          <td className="muted">{dateTime(o.updated_at)}</td>
          <td>{date(o.requested_date)}</td>
          <td className="num">{money(o.total)}</td>
        </tr>
      ))}</tbody>
    </table></div>
  )
}

export function AllOrders() {
  const nav = useNavigate()
  const [status, setStatus] = useState('active')
  const [s, setS] = useState('')
  const { data } = useLoad(() => {
    let query = supabase.from('orders').select('id,order_no,status,total,updated_at,requested_date,cancel_requested_reason,customers(name)').neq('status', 'draft').order('updated_at', { ascending: false }).limit(300)
    if (status === 'active') query = query.in('status', ACTIVE_STATUSES)
    else if (status !== 'all') query = query.eq('status', status)
    if (s.trim()) query = query.ilike('order_no', `%${s.trim()}%`)
    return q(query)
  }, [status, s])
  return (
    <>
      <PageHead title="All orders" sub="Every order with its internal status." />
      <div className="row">
        <select value={status} onChange={(e) => setStatus(e.target.value)} style={{ width: 240 }}>
          <option value="active">All open orders</option>
          <option value="all">Everything</option>
          {Object.entries(STATUS).filter(([k]) => k !== 'draft').map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
        </select>
        <input placeholder="Order number…" value={s} onChange={(e) => setS(e.target.value)} style={{ width: 200 }} />
      </div>
      <Card pad={false}><OrderTableStaff rows={data} onOpen={(o) => nav('/order/' + o.id)} /></Card>
    </>
  )
}

export function StaffOrder() {
  const { id } = useParams()
  const { role } = useAuth()
  const [modal, setModal] = useState(null)
  const [run, busy] = useAction()
  const { data, error, reload } = useLoad(async () => {
    const o = await q(supabase.from('orders').select('*, order_items(*), customers(*), addresses(label,line,instructions,regions(name))').eq('id', id).single())
    const [events, vr, inv, refunds, deliveries, history] = await Promise.all([
      q(supabase.from('order_events').select('*').eq('order_id', id).order('id')),
      q(supabase.from('validation_results').select('*').eq('order_id', id).eq('current', true).order('id')),
      role === 'warehouse' || role === 'dispatch' ? null : q(supabase.from('invoices').select('*, payments(*)').eq('order_id', id).maybeSingle()),
      role === 'warehouse' || role === 'dispatch' ? [] : q(supabase.from('refunds').select('*').eq('order_id', id)),
      ['ops', 'admin', 'dispatch'].includes(role) ? q(supabase.from('deliveries').select('*').eq('order_id', id).order('assigned_at')) : [],
      q(supabase.from('orders').select('id,status', { count: 'exact' }).eq('customer_id', o.customer_id).neq('status', 'draft')),
    ])
    return { o, events, vr, inv, refunds, deliveries, history }
  }, [id, role])
  if (!data) return <Loading error={error} />
  const { o, events, vr, inv, refunds, deliveries, history } = data
  const items = o.order_items.filter((i) => i.qty_ordered > 0)
  const ops = role === 'ops'
  const delivered = history.filter((h) => h.status === 'delivered').length
  const act = (fn, msg) => run(async () => { await fn(); reload() }, msg)
  const paid = inv?.status === 'paid' || inv?.status === 'credited'
  const refunded = refunds.reduce((s, r) => s + Number(r.amount), 0)

  const openProof = async (path) => window.open(await signedUrl('payment-proofs', path), '_blank', 'noopener')

  return (
    <>
      <PageHead title={o.order_no} sub={`${o.customers.name} · placed ${date(o.submitted_at || o.created_at)} · source: ${o.source}`}>
        <StatusBadge status={o.status} />
        {ops && o.status === 'pending_approval' && <>
          <button className="btn primary" disabled={busy} onClick={() => act(() => rpc('approve_order', { p_order: o.id, p_comment: null }), 'Approved. Stock reserved and invoice issued.')}>Approve</button>
          <button className="btn danger" onClick={() => setModal('reject')}>Reject</button>
        </>}
        {ops && !['out_for_delivery', 'delivered', 'cancelled', 'delivery_failed'].includes(o.status) && <button className="btn danger" onClick={() => setModal('cancel')}>Cancel order</button>}
        {role === 'warehouse' && ['paid', 'picking'].includes(o.status) && <Link className="btn primary" to={'/warehouse/pick/' + o.id}>Open picking</Link>}
      </PageHead>

      {o.cancel_requested_reason && (
        <div className="notice bad">
          <strong>The customer asked to cancel</strong>{o.cancel_requested_reason}
          {ops && <div className="row" style={{ marginTop: 6 }}>
            <button className="btn danger solid sm" onClick={() => setModal('cancel')}>Cancel and refund</button>
            <button className="btn sm" onClick={() => setModal('decline')}>Decline request</button>
          </div>}
        </div>
      )}
      {ops && o.status === 'payment_rejected' && inv && inv.payments.length >= o.payment_attempts_allowed && (
        <div className="notice warn row between"><span>The customer has used all {o.payment_attempts_allowed} proof uploads.</span>
          <button className="btn sm" onClick={() => setModal('attempt')}>Allow another upload</button></div>
      )}
      {ops && o.status === 'shortage_hold' && (
        <div className="notice warn">
          <strong>Shortage hold</strong> Customer choice: {o.shortage_choice ? o.shortage_choice.replace('_', ' ') : 'not answered yet'}.
          <div className="row" style={{ marginTop: 6 }}>
            <span className="muted small">Record the customer's choice if they called in:</span>
            <button className="btn sm" disabled={busy} onClick={() => act(() => rpc('choose_shortage', { p_order: o.id, p_choice: 'deliver_available' }), 'Recorded.')}>Deliver available</button>
            <button className="btn sm" disabled={busy} onClick={() => act(() => rpc('choose_shortage', { p_order: o.id, p_choice: 'wait_restock' }), 'Recorded.')}>Wait</button>
            <button className="btn sm danger" disabled={busy} onClick={() => act(() => rpc('choose_shortage', { p_order: o.id, p_choice: 'cancel_order' }), 'Cancelled.')}>Cancel</button>
          </div>
        </div>
      )}

      <div className="grid-main">
        <div className="stack-lg">
          <Card title="Items" pad={false}>
            <div className="table-wrap"><table>
              <thead><tr><th>Product</th><th className="num">Ordered</th><th className="num">Reserved</th><th className="num">Picked</th>{role !== 'warehouse' && role !== 'dispatch' && <><th className="num">Unit</th><th className="num">Total</th></>}</tr></thead>
              <tbody>{items.map((i) => (
                <tr key={i.id}>
                  <td><strong>{i.product_name}</strong><div className="muted small">{i.product_sku}</div></td>
                  <td className="num">{i.qty_ordered}</td><td className="num">{i.qty_reserved}</td><td className="num">{i.qty_picked}</td>
                  {role !== 'warehouse' && role !== 'dispatch' && <><td className="num">{money(i.unit_price)}</td><td className="num">{money(i.unit_price * i.qty_ordered)}</td></>}
                </tr>
              ))}</tbody>
            </table></div>
            {role !== 'warehouse' && role !== 'dispatch' && (
              <div className="card-body totals" style={{ maxWidth: 340, marginLeft: 'auto' }}>
                <div className="line"><span>Subtotal</span><span className="num">{money(o.subtotal)}</span></div>
                <div className="line"><span>Delivery</span><span className="num">{money(o.delivery_fee)}</span></div>
                <div className="line"><span>Tax</span><span className="num">{money(o.tax)}</span></div>
                <div className="line grand"><span>Total</span><span className="num">{money(o.total)}</span></div>
              </div>
            )}
          </Card>
          <Card title="Validation report" action={o.validation_outcome && <Badge tone={o.validation_outcome === 'fail' ? 'bad' : o.validation_outcome === 'warn' ? 'warn' : 'good'}>{o.validation_outcome}</Badge>}>
            {vr.length ? <ValidationReport results={vr} /> : <p className="muted">Not validated yet.</p>}
          </Card>
          {inv && (
            <Card title={`Invoice ${inv.invoice_no}`} action={<Badge tone={inv.status === 'paid' ? 'good' : 'warn'}>{inv.status}</Badge>}>
              <div className="stack">
                <div className="row between"><span className="muted">Due</span><span>{dateTime(inv.due_at)}</span></div>
                {inv.payments.length === 0 && <p className="muted">No payment uploaded yet.</p>}
                {inv.payments.sort((a, b) => a.attempt_no - b.attempt_no).map((p) => (
                  <div key={p.id} className="row between card card-pad" style={{ boxShadow: 'none' }}>
                    <div>Attempt {p.attempt_no}: <strong>{money(p.amount)}</strong> · ref <span className="mono">{p.reference}</span>
                      {p.reason && <div className="small" style={{ color: 'var(--bad)' }}>{p.reason}</div>}</div>
                    <div className="row">{p.proof_path && <button className="btn sm" onClick={() => openProof(p.proof_path)}>Proof</button>}<Badge tone={p.status === 'confirmed' ? 'good' : p.status === 'rejected' ? 'bad' : 'warn'}>{p.status}</Badge></div>
                  </div>
                ))}
                {refunds.map((r) => (
                  <div key={r.id} className="row between"><span>Refund: {r.reason}</span><span>{money(r.amount)} <Badge tone={r.status === 'paid' ? 'good' : 'warn'}>{r.status}</Badge></span></div>
                ))}
                {ops && paid && Number(inv.total) - refunded > 0 && <button className="btn sm" onClick={() => setModal('refund')}>Request a refund</button>}
              </div>
            </Card>
          )}
        </div>
        <div className="stack-lg">
          <Card title="Customer">
            <div className="stack">
              <strong>{o.customers.name}</strong>
              <div className="muted small">{o.customers.contact_name} · {o.customers.phone} · {o.customers.email}</div>
              <div className="row"><Badge tone="info">{history.length} orders</Badge><Badge tone="good">{delivered} delivered</Badge>{history.length <= 1 && <Badge tone="warn">New customer</Badge>}<Badge>{o.customers.payment_terms}</Badge></div>
              <div className="sep" />
              <div><span className="muted small">Deliver to</span><div>{o.addresses?.label}: {o.addresses?.line} ({o.addresses?.regions?.name})</div>{o.addresses?.instructions && <div className="muted small">{o.addresses.instructions}</div>}</div>
              <div><span className="muted small">Requested date</span><div>{date(o.requested_date)}</div></div>
              {o.notes && <div><span className="muted small">Notes</span><div>{o.notes}</div></div>}
            </div>
          </Card>
          {deliveries.length > 0 && (
            <Card title="Deliveries">
              <div className="stack">
                {deliveries.map((d) => (
                  <div key={d.id} className="small">{dateTime(d.assigned_at)} · {d.outcome || (d.current ? 'current' : '')}{d.failure_reason ? ` – ${d.failure_reason}` : ''}</div>
                ))}
                {ops && ['packed', 'assigned', 'out_for_delivery', 'delivery_failed'].includes(o.status) && (
                  <div className="row">
                    <button className="btn sm" onClick={() => setModal('reissue')}>Re-issue code</button>
                    {o.status === 'out_for_delivery' && <button className="btn sm danger" onClick={() => setModal('override')}>Override delivery</button>}
                  </div>
                )}
              </div>
            </Card>
          )}
          <Card title="Timeline"><Timeline events={events} /></Card>
        </div>
      </div>

      {modal === 'reject' && <ReasonModal title={`Reject ${o.order_no}`} label="Reason (the customer sees this)" danger confirm="Reject" onClose={() => setModal(null)}
        onSubmit={(r) => rpc('reject_order', { p_order: o.id, p_reason: r }).then(reload)} />}
      {modal === 'cancel' && <ReasonModal title={`Cancel ${o.order_no}`} label="Reason (the customer sees this)" danger confirm="Cancel order" onClose={() => setModal(null)}
        onSubmit={(r) => rpc('ops_cancel_order', { p_order: o.id, p_reason: r }).then(reload)}>
        {paid && <div className="notice warn">This order is paid. A refund request for the unrefunded amount will go to Finance automatically.</div>}
      </ReasonModal>}
      {modal === 'decline' && <ReasonModal title="Decline cancellation" label="Message to the customer" onClose={() => setModal(null)}
        onSubmit={(r) => rpc('decline_cancel_request', { p_order: o.id, p_note: r }).then(reload)} />}
      {modal === 'attempt' && <ReasonModal title="Allow another proof upload" label="Message to the customer" required={false} onClose={() => setModal(null)}
        onSubmit={(r) => rpc('allow_payment_attempt', { p_order: o.id, p_note: r }).then(reload)} />}
      {modal === 'reissue' && <ReasonModal title="Re-issue delivery code" label="Reason" onClose={() => setModal(null)}
        options={['Customer lost the code', 'Code locked after wrong attempts', 'Code expired', 'Other']}
        onSubmit={(r) => rpc('reissue_code', { p_order: o.id, p_reason: r }).then(reload)} />}
      {modal === 'override' && <ReasonModal title="Override: mark delivered without a code" label="Explain exactly why (logged and visible to the administrator)" minLength={10} danger confirm="Mark delivered" onClose={() => setModal(null)}
        onSubmit={(r) => rpc('override_delivery', { p_order: o.id, p_reason: r }).then(reload)}>
        <div className="notice warn">Use only when you have confirmed the handover another way (e.g. a call with the customer).</div>
      </ReasonModal>}
      {modal === 'refund' && <RefundModal o={o} max={Number(inv.total) - refunded} onClose={() => setModal(null)} onDone={reload} />}
    </>
  )
}

function RefundModal({ o, max, onClose, onDone }) {
  const [amount, setAmount] = useState('')
  return (
    <ReasonModal title={`Refund request for ${o.order_no}`} label="Reason" onClose={onClose}
      onSubmit={async (r) => { await rpc('request_refund', { p_order: o.id, p_amount: Number(amount), p_reason: r }); onDone() }}>
      <label className="field">Amount <span className="hint">Up to {money(max)}</span><input type="number" step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} /></label>
    </ReasonModal>
  )
}
