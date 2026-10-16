import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import toast from 'react-hot-toast'
import { supabase, rpc, uploadFile } from '../../lib/supabase'
import { useAuth } from '../../context/AuthContext'
import { money, date, dateTime, hoursLeft, STATUS } from '../../lib/format'
import { Card, PageHead, Kpi, StatusBadge, Badge, Empty, Loading, Modal, ReasonModal, Timeline, ValidationReport, useLoad, q, countOf, useAction } from '../../components/ui'

const ACTION_NEEDED = ['validation_failed', 'rejected', 'payment_rejected', 'shortage_hold', 'awaiting_payment']

export function CustomerDashboard() {
  const { customer } = useAuth()
  const nav = useNavigate()
  const { data } = useLoad(async () => {
    const [open, pay, out, recent] = await Promise.all([
      countOf(supabase.from('orders').select('id', { count: 'exact', head: true }).not('status', 'in', '(draft,delivered,cancelled)')),
      countOf(supabase.from('orders').select('id', { count: 'exact', head: true }).in('status', ['awaiting_payment', 'payment_rejected'])),
      countOf(supabase.from('orders').select('id', { count: 'exact', head: true }).eq('status', 'out_for_delivery')),
      q(supabase.from('orders').select('id,order_no,status,total,created_at,requested_date').neq('status', 'draft').order('created_at', { ascending: false }).limit(8)),
    ])
    const actions = await q(supabase.from('orders').select('id,order_no,status').in('status', ACTION_NEEDED).order('updated_at', { ascending: false }))
    return { open, pay, out, recent, actions }
  })
  const actionText = {
    validation_failed: 'Fix the order and resubmit', rejected: 'Rejected – see reason and resubmit', awaiting_payment: 'Pay and upload proof',
    payment_rejected: 'Payment proof not accepted – upload again', shortage_hold: 'Choose what to do about short items',
  }
  return (
    <>
      <PageHead hero title={`Welcome, ${customer?.contact_name?.split(' ')[0] || ''}`} sub={customer?.name}>
        <Link className="btn primary" to="/new-order">New order</Link>
      </PageHead>
      <div className="kpis">
        <Kpi label="Open orders" value={data?.open} to="/orders" />
        <Kpi label="Awaiting payment" value={data?.pay} to="/invoices" alert={data?.pay > 0} />
        <Kpi label="Out for delivery" value={data?.out} to="/codes" />
        <Kpi label="Delivery codes ready" value={data?.out} to="/codes" />
      </div>
      <div className="grid-main">
        <Card title="My orders" pad={false} action={<Link to="/orders">All orders</Link>}>
          <OrderTable rows={data?.recent} onOpen={(o) => nav('/orders/' + o.id)} />
        </Card>
        <Card title="Needs your action">
          {!data ? <Loading /> : data.actions.length === 0 ? <Empty>Nothing needs your attention.</Empty> : (
            <div className="stack">
              {data.actions.map((o) => (
                <Link key={o.id} to={o.status === 'awaiting_payment' || o.status === 'payment_rejected' ? '/invoices' : '/orders/' + o.id} className="notice warn" style={{ textDecoration: 'none' }}>
                  <strong>{o.order_no}</strong><span>{actionText[o.status]}</span>
                </Link>
              ))}
            </div>
          )}
        </Card>
      </div>
    </>
  )
}

function OrderTable({ rows, onOpen }) {
  if (!rows) return <Loading />
  if (!rows.length) return <Empty>No orders yet. <Link to="/new-order">Place your first order</Link>.</Empty>
  return (
    <div className="table-wrap">
      <table>
        <thead><tr><th>Order</th><th>Status</th><th>Placed</th><th>Delivery date</th><th className="num">Total</th></tr></thead>
        <tbody>
          {rows.map((o) => (
            <tr key={o.id} className="click" onClick={() => onOpen(o)}>
              <td><strong>{o.order_no}</strong></td>
              <td><StatusBadge status={o.status} customer /></td>
              <td>{date(o.created_at)}</td>
              <td>{date(o.requested_date)}</td>
              <td className="num">{money(o.total)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function MyOrders() {
  const nav = useNavigate()
  const [filter, setFilter] = useState('open')
  const { data } = useLoad(() => {
    let query = supabase.from('orders').select('id,order_no,status,total,created_at,requested_date').order('created_at', { ascending: false }).limit(200)
    if (filter === 'open') query = query.not('status', 'in', '(delivered,cancelled)')
    if (filter === 'done') query = query.in('status', ['delivered', 'cancelled'])
    return q(query)
  }, [filter])
  return (
    <>
      <PageHead title="My orders"><Link className="btn primary" to="/new-order">New order</Link></PageHead>
      <div className="tabs">
        {[['open', 'Open'], ['done', 'Completed'], ['all', 'All']].map(([k, l]) => <button key={k} className={filter === k ? 'on' : ''} onClick={() => setFilter(k)}>{l}</button>)}
      </div>
      <Card pad={false}><OrderTable rows={data} onOpen={(o) => nav(o.status === 'draft' ? '/new-order?edit=' + o.id : '/orders/' + o.id)} /></Card>
    </>
  )
}

export function OrderDetail() {
  const { id } = useParams()
  const nav = useNavigate()
  const [modal, setModal] = useState(null)
  const [run, busy] = useAction()
  const { data, error, reload } = useLoad(async () => {
    const [o, events, vr, refunds, inv] = await Promise.all([
      q(supabase.from('orders').select('*, order_items(*), addresses(label,line)').eq('id', id).single()),
      q(supabase.from('order_events').select('*').eq('order_id', id).order('id')),
      q(supabase.from('validation_results').select('*').eq('order_id', id).eq('current', true).order('id')),
      q(supabase.from('refunds').select('*').eq('order_id', id)),
      q(supabase.from('invoices').select('*').eq('order_id', id).maybeSingle()),
    ])
    return { o, events, vr, refunds, inv }
  }, [id])
  if (!data) return <Loading error={error} />
  const { o, events, vr, refunds, inv } = data
  const items = o.order_items.filter((i) => i.qty_ordered > 0)
  const editable = ['draft', 'validation_failed', 'rejected'].includes(o.status)
  const cancellable = !['out_for_delivery', 'delivered', 'cancelled', 'delivery_failed'].includes(o.status)
  const lastReject = [...events].reverse().find((e) => e.to_status === 'rejected')

  return (
    <>
      <PageHead title={o.order_no} sub={`Placed ${date(o.created_at)} · delivery ${date(o.requested_date)} · ${o.addresses?.label || ''}`}>
        <StatusBadge status={o.status} customer />
        {editable && <Link className="btn primary" to={'/new-order?edit=' + o.id}>Edit and resubmit</Link>}
        <button className="btn" disabled={busy} onClick={() => run(async () => nav('/new-order?edit=' + (await rpc('reorder', { p_order: o.id }))), 'Copied into a new order.')}>Reorder</button>
        {cancellable && !o.cancel_requested_reason && <button className="btn danger" onClick={() => setModal('cancel')}>Cancel order</button>}
      </PageHead>

      {o.status === 'rejected' && lastReject && <div className="notice bad"><strong>Rejected by our Ops Desk</strong>{lastReject.note}</div>}
      {o.status === 'validation_failed' && <div className="notice bad"><strong>Some checks failed</strong><ValidationReport results={vr.filter((r) => r.severity === 'fail')} compact /></div>}
      {o.cancel_requested_reason && <div className="notice info">You asked to cancel this order. The Ops Desk will reply shortly.</div>}
      {(o.status === 'awaiting_payment' || o.status === 'payment_rejected') && (
        <div className="notice warn row between"><span>Payment due {inv && hoursLeft(inv.due_at)}.</span><Link className="btn primary sm" to="/invoices">Pay now</Link></div>
      )}
      {o.status === 'out_for_delivery' && <div className="notice good row between"><span>Your order is on the way.</span><Link className="btn primary sm" to="/codes">Show delivery code</Link></div>}
      {o.status === 'shortage_hold' && <ShortageChoice order={o} items={items} onDone={reload} />}

      <div className="grid-main">
        <Card title="Items" pad={false}>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Product</th><th className="num">Ordered</th>{['packed', 'assigned', 'out_for_delivery', 'delivered', 'shortage_hold'].includes(o.status) && <th className="num">Packed</th>}<th className="num">Unit price</th><th className="num">Total</th></tr></thead>
              <tbody>
                {items.map((i) => (
                  <tr key={i.id}>
                    <td><strong>{i.product_name}</strong><div className="muted small">{i.product_sku}</div></td>
                    <td className="num">{i.qty_ordered}</td>
                    {['packed', 'assigned', 'out_for_delivery', 'delivered', 'shortage_hold'].includes(o.status) && <td className="num">{i.qty_picked}</td>}
                    <td className="num">{money(i.unit_price)}</td>
                    <td className="num">{money(i.unit_price * i.qty_ordered)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="card-body totals" style={{ maxWidth: 360, marginLeft: 'auto' }}>
            <div className="line"><span>Subtotal</span><span className="num">{money(o.subtotal)}</span></div>
            <div className="line"><span>Delivery fee</span><span className="num">{money(o.delivery_fee)}</span></div>
            <div className="line"><span>Tax</span><span className="num">{money(o.tax)}</span></div>
            <div className="line grand"><span>Total</span><span className="num">{money(o.total)}</span></div>
            {refunds.map((r) => (
              <div className="line" key={r.id}><span>Refund {r.status === 'paid' ? `(paid, ${r.credit_note_no})` : '(being processed)'}</span><span className="num">−{money(r.amount)}</span></div>
            ))}
          </div>
        </Card>
        <Card title="Timeline"><Timeline events={events} customer /></Card>
      </div>

      {modal === 'cancel' && (
        <ReasonModal title="Cancel this order?" label="Why are you cancelling? (optional)" required={false} danger confirm="Cancel order"
          onClose={() => setModal(null)}
          onSubmit={async (reason) => {
            const r = await rpc('cancel_order', { p_order: o.id, p_reason: reason })
            toast.success(r === 'cancelled' ? 'Order cancelled.' : 'Request sent to the Ops Desk.')
            reload()
          }}>
          <p className="muted">{['paid', 'picking', 'shortage_hold', 'packed', 'assigned', 'payment_verification'].includes(o.status)
            ? 'Payment is already in. Our Ops Desk will review the request and refund you if it is cancelled.'
            : 'Nothing has been paid, so the order is cancelled straight away.'}</p>
        </ReasonModal>
      )}
    </>
  )
}

function ShortageChoice({ order, items, onDone }) {
  const [run, busy] = useAction()
  const short = items.filter((i) => i.qty_picked < i.qty_ordered)
  const value = short.reduce((s, i) => s + (i.qty_ordered - i.qty_picked) * i.unit_price, 0)
  const choose = (c) => run(async () => { await rpc('choose_shortage', { p_order: order.id, p_choice: c }); onDone() }, 'Choice recorded.')
  return (
    <Card title="Some items are short">
      <div className="stack">
        <p>The warehouse could not find everything you ordered:</p>
        <ul style={{ margin: 0 }}>{short.map((i) => <li key={i.id}>{i.product_name}: {i.qty_picked} of {i.qty_ordered} available</li>)}</ul>
        {order.shortage_choice === 'wait_restock' ? (
          <div className="notice info">You chose to wait for restock. We will continue as soon as the stock arrives. You can still change your mind:</div>
        ) : <p className="muted">Choose what we should do. Short items are worth {money(value)} before tax.</p>}
        <div className="row">
          <button className="btn primary" disabled={busy} onClick={() => choose('deliver_available')}>Deliver what is available, refund the rest</button>
          {order.shortage_choice !== 'wait_restock' && <button className="btn" disabled={busy} onClick={() => choose('wait_restock')}>Wait for restock</button>}
          <button className="btn danger" disabled={busy} onClick={() => choose('cancel_order')}>Cancel the order (full refund)</button>
        </div>
      </div>
    </Card>
  )
}

export function Invoices() {
  const [pay, setPay] = useState(null)
  const { data, reload } = useLoad(async () => {
    const [inv, bank] = await Promise.all([
      q(supabase.from('invoices').select('*, orders(order_no,status,payment_attempts_allowed), payments(*)').order('created_at', { ascending: false }).limit(100)),
      q(supabase.from('settings').select('value').eq('key', 'bank_details').single()),
    ])
    return { inv, bank: bank.value }
  })
  if (!data) return <Loading />
  const due = data.inv.filter((i) => ['awaiting_payment', 'payment_rejected'].includes(i.orders.status))
  return (
    <>
      <PageHead title="Invoices & pay" sub="Pay by bank transfer, then upload the proof or enter the transfer reference." />
      <Card title="Pay to">
        <div className="grid-3">
          <div><div className="muted small">Bank</div><strong>{data.bank.bank}</strong></div>
          <div><div className="muted small">Account name</div><strong>{data.bank.account_name}</strong></div>
          <div><div className="muted small">Account number</div><strong className="mono" style={{ fontSize: 16 }}>{data.bank.account_no}</strong></div>
        </div>
        <p className="muted small" style={{ marginTop: 10 }}>Use the invoice number as the transfer narration.</p>
      </Card>
      {due.length > 0 && (
        <Card title="To pay" pad={false}>
          <div className="table-wrap"><table>
            <thead><tr><th>Invoice</th><th>Order</th><th>Due</th><th>Status</th><th className="num">Amount</th><th /></tr></thead>
            <tbody>{due.map((i) => {
              const last = [...i.payments].sort((a, b) => b.attempt_no - a.attempt_no)[0]
              const left = i.orders.payment_attempts_allowed - i.payments.length
              return (
                <tr key={i.id}>
                  <td><Link to={'/invoice/' + i.id}><strong>{i.invoice_no}</strong></Link></td>
                  <td><Link to={'/orders/' + i.order_id}>{i.orders.order_no}</Link></td>
                  <td>{dateTime(i.due_at)}<div className="small" style={{ color: 'var(--warn)' }}>{hoursLeft(i.due_at)}</div></td>
                  <td><StatusBadge status={i.orders.status} customer />
                    {last?.status === 'rejected' && <div className="small" style={{ color: 'var(--bad)' }}>Not accepted: {last.reason}</div>}
                  </td>
                  <td className="num"><strong>{money(i.total)}</strong></td>
                  <td>{left > 0 ? <button className="btn primary sm" onClick={() => setPay(i)}>Upload proof</button> : <span className="muted small">Ops Desk will contact you</span>}</td>
                </tr>
              )
            })}</tbody>
          </table></div>
        </Card>
      )}
      <Card title="All invoices" pad={false}>
        {data.inv.length === 0 ? <Empty>No invoices yet. An invoice is issued when an order is approved.</Empty> : (
          <div className="table-wrap"><table>
            <thead><tr><th>Invoice</th><th>Order</th><th>Issued</th><th>Status</th><th className="num">Total</th></tr></thead>
            <tbody>{data.inv.map((i) => (
              <tr key={i.id}>
                <td><Link to={'/invoice/' + i.id}>{i.invoice_no}</Link></td><td><Link to={'/orders/' + i.order_id}>{i.orders.order_no}</Link></td><td>{date(i.created_at)}</td>
                <td><Badge tone={i.status === 'paid' ? 'good' : i.status === 'issued' ? 'warn' : 'muted'}>{i.status}</Badge></td>
                <td className="num">{money(i.total)}</td>
              </tr>
            ))}</tbody>
          </table></div>
        )}
      </Card>
      {pay && <PayModal invoice={pay} onClose={() => setPay(null)} onDone={() => { setPay(null); reload() }} />}
    </>
  )
}

function PayModal({ invoice, onClose, onDone }) {
  const { user } = useAuth()
  const [amount, setAmount] = useState(invoice.total)
  const [ref, setRef] = useState('')
  const [file, setFile] = useState(null)
  const [busy, setBusy] = useState(false)
  const submit = async () => {
    setBusy(true)
    try {
      if (file && file.size > 5 * 1024 * 1024) throw new Error('The file is larger than 5 MB.')
      const path = file ? await uploadFile('payment-proofs', file, user.id, invoice.id) : null
      await rpc('upload_payment', { p_invoice: invoice.id, p_amount: Number(amount), p_reference: ref, p_proof_path: path })
      toast.success('Sent to Finance for confirmation.')
      onDone()
    } catch (e) {
      toast.error(e.message)
      setBusy(false)
    }
  }
  return (
    <Modal title={`Pay ${invoice.invoice_no}`} onClose={onClose} footer={<>
      <button className="btn" onClick={onClose}>Cancel</button>
      <button className="btn primary" disabled={busy || !ref.trim() || !(Number(amount) > 0)} onClick={submit}>{busy ? 'Sending…' : 'Send to Finance'}</button>
    </>}>
      <div className="row between"><span>Invoice total</span><strong>{money(invoice.total)}</strong></div>
      <label className="field">Amount you transferred<input type="number" step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} /></label>
      {Number(amount) !== Number(invoice.total) && <div className="notice warn">This is different from the invoice total. Finance may reject a part payment.</div>}
      <label className="field">Transfer reference<input value={ref} onChange={(e) => setRef(e.target.value)} placeholder="e.g. FT2610160045" /></label>
      <label className="field">Proof of payment <span className="hint">Receipt or screenshot, PDF/JPG/PNG up to 5 MB (optional if you entered the reference)</span>
        <input type="file" accept=".pdf,.jpg,.jpeg,.png" onChange={(e) => setFile(e.target.files[0])} style={{ paddingTop: 6 }} />
      </label>
    </Modal>
  )
}

export function DeliveryCodes() {
  const { data } = useLoad(async () => {
    const orders = await q(supabase.from('orders').select('id,order_no,status,requested_date,addresses(label,line)').in('status', ['packed', 'assigned', 'out_for_delivery']).order('requested_date'))
    const codes = await q(supabase.from('delivery_code_reveals').select('order_id,code'))
    return { orders, codes: Object.fromEntries(codes.map((c) => [c.order_id, c.code])) }
  })
  if (!data) return <Loading />
  return (
    <>
      <PageHead title="Delivery codes" sub="Give the code to the driver only when you have checked the goods. The driver cannot see it." />
      {data.orders.length === 0 && <Card><Empty>No orders on the way right now.</Empty></Card>}
      <div className="grid-2">
        {data.orders.map((o) => (
          <Card key={o.id} title={o.order_no} action={<StatusBadge status={o.status} customer />}>
            <div className="stack">
              <div className="muted">{o.addresses?.label} – {o.addresses?.line}</div>
              {data.codes[o.id] ? <div className="code-box" aria-label="Delivery code">{data.codes[o.id]}</div>
                : <div className="notice info">The code appears here when the driver leaves the warehouse with your order.</div>}
            </div>
          </Card>
        ))}
      </div>
    </>
  )
}

export function Catalogue() {
  const [s, setS] = useState('')
  const { data } = useLoad(() => rpc('get_catalogue'))
  if (!data) return <Loading />
  const rows = data.filter((p) => (p.name + p.sku).toLowerCase().includes(s.toLowerCase()))
  return (
    <>
      <PageHead title="Catalogue" sub="Fixed prices from the current price list."><Link className="btn primary" to="/new-order">New order</Link></PageHead>
      <input placeholder="Search…" value={s} onChange={(e) => setS(e.target.value)} style={{ maxWidth: 360 }} />
      <Card pad={false}>
        <div className="table-wrap"><table>
          <thead><tr><th>Product</th><th>SKU</th><th>Unit</th><th className="num">Price</th><th>Order limits</th><th>Availability</th></tr></thead>
          <tbody>{rows.map((p) => (
            <tr key={p.id}>
              <td><strong>{p.name}</strong></td><td className="mono">{p.sku}</td><td>{p.unit}</td><td className="num">{money(p.price)}</td>
              <td className="muted">{p.min_qty}–{p.max_qty}</td>
              <td>{p.stock_status === 'out_of_stock' ? <Badge tone="bad">Out of stock</Badge> : p.stock_status === 'low_stock' ? <Badge tone="warn">Only {p.only_left} left</Badge> : <Badge tone="good">In stock</Badge>}</td>
            </tr>
          ))}</tbody>
        </table></div>
      </Card>
    </>
  )
}

export function Profile() {
  const { customer } = useAuth()
  const [edit, setEdit] = useState(null)
  const { data, reload } = useLoad(async () => {
    const [addr, regions] = await Promise.all([
      q(supabase.from('addresses').select('*, regions(name,delivery_fee)').eq('active', true).order('label')),
      q(supabase.from('regions').select('*').eq('active', true).order('name')),
    ])
    return { addr, regions }
  })
  if (!data) return <Loading />
  const allowed = customer.allowed_region_ids?.length ? data.regions.filter((r) => customer.allowed_region_ids.includes(r.id)) : data.regions
  return (
    <>
      <PageHead title="Profile & addresses" />
      <div className="grid-2">
        <Card title="Company">
          <div className="stack">
            {[['Name', customer.name], ['Registration no.', customer.reg_no], ['Contact', customer.contact_name], ['Phone', customer.phone], ['E-mail', customer.email], ['Payment terms', customer.payment_terms]].map(([k, v]) => (
              <div className="row between" key={k}><span className="muted">{k}</span><span>{v}</span></div>
            ))}
          </div>
        </Card>
        <Card title="Delivery addresses" action={<button className="btn sm primary" onClick={() => setEdit({})}>Add address</button>}>
          {data.addr.length === 0 ? <Empty>No saved addresses yet.</Empty> : (
            <div className="stack">
              {data.addr.map((a) => (
                <div key={a.id} className="row between card card-pad" style={{ boxShadow: 'none' }}>
                  <div><strong>{a.label}</strong><div className="muted small">{a.line} · {a.regions?.name} ({money(a.regions?.delivery_fee)} delivery)</div>{a.instructions && <div className="small">{a.instructions}</div>}</div>
                  <div className="row">
                    <button className="btn sm" onClick={() => setEdit(a)}>Edit</button>
                    <button className="btn sm danger" onClick={async () => { await rpc('remove_address', { p_id: a.id }); reload() }}>Remove</button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
      {edit && <AddressModal a={edit} regions={allowed} onClose={() => setEdit(null)} onDone={() => { setEdit(null); reload() }} />}
    </>
  )
}

function AddressModal({ a, regions, onClose, onDone }) {
  const [f, setF] = useState({ label: a.label || '', line: a.line || '', region: a.region_id || '', instructions: a.instructions || '' })
  const [run, busy] = useAction()
  return (
    <Modal title={a.id ? 'Edit address' : 'Add address'} onClose={onClose} footer={<>
      <button className="btn" onClick={onClose}>Cancel</button>
      <button className="btn primary" disabled={busy} onClick={() => run(async () => {
        await rpc('save_address', { p_id: a.id || null, p_label: f.label, p_line: f.line, p_region: Number(f.region) || null, p_instructions: f.instructions })
        onDone()
      }, 'Saved.')}>Save</button>
    </>}>
      <label className="field">Label<input value={f.label} placeholder="Head office" onChange={(e) => setF({ ...f, label: e.target.value })} /></label>
      <label className="field">Address<input value={f.line} onChange={(e) => setF({ ...f, line: e.target.value })} /></label>
      <label className="field">Delivery region
        <select value={f.region} onChange={(e) => setF({ ...f, region: e.target.value })}>
          <option value="">Choose…</option>
          {regions.map((r) => <option key={r.id} value={r.id}>{r.name} – {money(r.delivery_fee)}</option>)}
        </select>
      </label>
      <label className="field">Instructions for the driver<input value={f.instructions} onChange={(e) => setF({ ...f, instructions: e.target.value })} /></label>
    </Modal>
  )
}

export { STATUS }
