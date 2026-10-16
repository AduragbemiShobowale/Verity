import { useState } from 'react'
import { Link } from 'react-router-dom'
import toast from 'react-hot-toast'
import { supabase, rpc, adminUsers, signedUrl } from '../../lib/supabase'
import { useAuth } from '../../context/AuthContext'
import { money, date, dateTime, ago, ROLE_LABEL, STATUS, ACTIVE_STATUSES } from '../../lib/format'
import { Card, PageHead, Kpi, Badge, Empty, Loading, Modal, ReasonModal, StatusBadge, useLoad, q, countOf, useAction } from '../../components/ui'

const head = () => ({ count: 'exact', head: true })
const CUSTOMER_TONE = { active: 'good', awaiting_review: 'warn', more_info: 'warn', rejected: 'bad', on_hold: 'muted', blocked: 'bad' }

export function AdminDashboard() {
  const { data } = useLoad(async () => {
    const today = new Date(); today.setHours(0, 0, 0, 0)
    const [toReview, active, staff, ordersToday, regs, byStatus] = await Promise.all([
      countOf(supabase.from('customers').select('id', head()).eq('status', 'awaiting_review')),
      countOf(supabase.from('customers').select('id', head()).eq('status', 'active')),
      countOf(supabase.from('profiles').select('id', head()).neq('role', 'customer').eq('status', 'active')),
      countOf(supabase.from('orders').select('id', head()).gte('submitted_at', today.toISOString())),
      q(supabase.from('customers').select('id,name,created_at,status').in('status', ['awaiting_review', 'more_info']).order('created_at').limit(6)),
      q(supabase.from('orders').select('status').neq('status', 'draft')),
    ])
    const tally = {}
    byStatus.forEach((o) => { tally[o.status] = (tally[o.status] || 0) + 1 })
    return { toReview, active, staff, ordersToday, regs, tally, total: byStatus.length }
  })
  return (
    <>
      <PageHead hero title="Administrator console" sub="Accounts, catalogue, prices, rules and the audit trail. Admin does not approve orders or confirm payments." />
      <div className="kpis">
        <Kpi label="Registrations to review" value={data?.toReview} to="/admin/registrations" alert={data?.toReview > 0} />
        <Kpi label="Active customers" value={data?.active} to="/admin/customers" />
        <Kpi label="Internal users" value={data?.staff} to="/admin/users" />
        <Kpi label="Orders today" value={data?.ordersToday} to="/ops/orders" />
      </div>
      <div className="grid-main">
        <Card title="Orders by status" >
          {!data ? <Loading /> : (
            <div className="stack">
              {Object.keys(STATUS).filter((s) => data.tally[s]).map((s) => (
                <div key={s}>
                  <div className="row between small"><StatusBadge status={s} /><strong>{data.tally[s]}</strong></div>
                  <div className="bar" style={{ marginTop: 4 }}><span style={{ width: `${(data.tally[s] / data.total) * 100}%` }} /></div>
                </div>
              ))}
              {data.total === 0 && <Empty>No orders yet.</Empty>}
            </div>
          )}
        </Card>
        <Card title="Registration review" action={<Link to="/admin/registrations">Open</Link>}>
          {!data ? <Loading /> : data.regs.length === 0 ? <Empty>No applications waiting.</Empty> : (
            <div className="stack">{data.regs.map((c) => (
              <Link key={c.id} to={'/admin/registrations?c=' + c.id} className="row between" style={{ color: 'inherit' }}>
                <span><strong>{c.name}</strong> <span className="muted small">{ago(c.created_at)}</span></span><Badge tone="warn">{c.status.replace('_', ' ')}</Badge>
              </Link>
            ))}</div>
          )}
        </Card>
      </div>
    </>
  )
}

export function Registrations() {
  const params = new URLSearchParams(window.location.search)
  const [sel, setSel] = useState(params.get('c'))
  const [tab, setTab] = useState('awaiting_review')
  const [modal, setModal] = useState(null)
  const { data, reload } = useLoad(async () => {
    const [cust, regions] = await Promise.all([
      q(supabase.from('customers').select('*, registration_applications(*)').eq('status', tab).order('created_at')),
      q(supabase.from('regions').select('*').eq('active', true).order('name')),
    ])
    return { cust, regions }
  }, [tab])
  const cur = data?.cust.find((c) => c.id === sel) || data?.cust[0]
  const app = cur?.registration_applications?.sort((a, b) => new Date(b.created_at) - new Date(a.created_at))[0]
  const open = async (path) => window.open(await signedUrl('registration-docs', path), '_blank', 'noopener')
  return (
    <>
      <PageHead title="Registrations" sub="Screening rules run first; you decide everything they send to review." />
      <div className="tabs">{[['awaiting_review', 'To review'], ['more_info', 'Waiting for applicant'], ['on_hold', 'On hold'], ['rejected', 'Rejected']].map(([k, l]) => <button key={k} className={tab === k ? 'on' : ''} onClick={() => { setTab(k); setSel(null) }}>{l}</button>)}</div>
      {!data ? <Loading /> : data.cust.length === 0 ? <Card><Empty>Nothing here.</Empty></Card> : (
        <div className="grid-main" style={{ gridTemplateColumns: 'minmax(0,1fr) minmax(0,1.6fr)' }}>
          <Card pad={false}><div className="table-wrap"><table><tbody>{data.cust.map((c) => (
            <tr key={c.id} className={`click ${cur?.id === c.id ? 'selected' : ''}`} onClick={() => setSel(c.id)}>
              <td><strong>{c.name}</strong><div className="muted small">{c.reg_no} · {ago(c.created_at)}</div></td>
            </tr>
          ))}</tbody></table></div></Card>
          {cur && (
            <Card title={cur.name}>
              <div className="stack-lg">
                <div className="grid-2">
                  {[['Registration no.', cur.reg_no], ['Industry', cur.industry], ['Contact', cur.contact_name], ['Phone', cur.phone], ['E-mail', cur.email], ['Address', cur.address], ['Expected orders / month', cur.expected_volume], ['Applied', dateTime(cur.created_at)]].map(([k, v]) => (
                    <div key={k}><div className="muted small">{k}</div><div>{v || '—'}</div></div>
                  ))}
                </div>
                {app && (
                  <div className="stack">
                    <h3>Rule results <span className="muted small">({app.outcome.replace('_', ' ')})</span></h3>
                    {(app.rule_results || []).map((r, i) => (
                      <div key={i} className={`vr-item ${r.result}`}><strong>{r.result === 'pass' ? '✓' : r.result === 'warn' ? '!' : '✕'}</strong><div>{r.message}</div></div>
                    ))}
                    <h3>Documents</h3>
                    {app.documents?.length ? <div className="row">{app.documents.map((d) => <button key={d} className="btn sm" onClick={() => open(d)}>{d.split('/').pop().replace(/^\d+-/, '')}</button>)}</div> : <p className="muted">None.</p>}
                  </div>
                )}
                {cur.admin_note && <div className="notice info"><strong>Last note</strong>{cur.admin_note}</div>}
                <div className="row">
                  <button className="btn primary" onClick={() => setModal('accept')}>Accept</button>
                  <button className="btn" onClick={() => setModal('more_info')}>Ask for more info</button>
                  <button className="btn" onClick={() => setModal('hold')}>Hold</button>
                  <button className="btn danger" onClick={() => setModal('reject')}>Reject</button>
                </div>
              </div>
            </Card>
          )}
        </div>
      )}
      {modal === 'accept' && cur && <AcceptModal c={cur} regions={data.regions} onClose={() => setModal(null)} onDone={() => { setModal(null); setSel(null); reload() }} />}
      {['reject', 'more_info', 'hold'].includes(modal) && cur && (
        <ReasonModal title={{ reject: 'Reject application', more_info: 'Ask for more information', hold: 'Put on hold' }[modal]}
          label={modal === 'more_info' ? 'What is missing? (the applicant sees this)' : 'Reason (the applicant sees this)'}
          required={modal !== 'hold'} danger={modal === 'reject'} onClose={() => setModal(null)}
          onSubmit={async (note) => { await rpc('decide_registration', { p_customer: cur.id, p_decision: modal, p_note: note, p_terms: {} }); setSel(null); reload() }} />
      )}
    </>
  )
}

function TermsFields({ t, setT, regions }) {
  return (
    <>
      <label className="field">Payment terms
        <select value={t.payment_terms} onChange={(e) => setT({ ...t, payment_terms: e.target.value })}>
          <option value="prepaid">Prepaid (pay before fulfilment)</option>
          <option value="credit" disabled>Credit – later phase</option>
        </select>
      </label>
      <label className="field">Credit limit (for the later credit phase)<input type="number" value={t.credit_limit} onChange={(e) => setT({ ...t, credit_limit: e.target.value })} /></label>
      <div className="field">Delivery regions <span className="hint">None ticked = all regions</span>
        <div className="row">{regions.map((r) => (
          <label key={r.id} className="row" style={{ gap: 4 }}><input type="checkbox" checked={t.allowed_region_ids.includes(r.id)}
            onChange={(e) => setT({ ...t, allowed_region_ids: e.target.checked ? [...t.allowed_region_ids, r.id] : t.allowed_region_ids.filter((x) => x !== r.id) })} />{r.name}</label>
        ))}</div>
      </div>
      <label className="row"><input type="checkbox" checked={t.trusted} onChange={(e) => setT({ ...t, trusted: e.target.checked })} /> Trusted customer</label>
    </>
  )
}

function AcceptModal({ c, regions, onClose, onDone }) {
  const [t, setT] = useState({ payment_terms: 'prepaid', credit_limit: 0, allowed_region_ids: [], trusted: false })
  const [note, setNote] = useState('')
  const [run, busy] = useAction()
  return (
    <Modal title={`Accept ${c.name}`} onClose={onClose} footer={<>
      <button className="btn" onClick={onClose}>Cancel</button>
      <button className="btn primary" disabled={busy} onClick={() => run(async () => { await rpc('decide_registration', { p_customer: c.id, p_decision: 'accept', p_note: note, p_terms: { ...t, credit_limit: Number(t.credit_limit) } }); onDone() }, 'Accepted. The customer has been notified.')}>Accept and activate</button>
    </>}>
      <TermsFields t={t} setT={setT} regions={regions} />
      <label className="field">Note (optional)<input value={note} onChange={(e) => setNote(e.target.value)} /></label>
    </Modal>
  )
}

export function Users() {
  const { user } = useAuth()
  const [create, setCreate] = useState(null)
  const [secret, setSecret] = useState(null)
  const [run, busy] = useAction()
  const [filter, setFilter] = useState('staff')
  const { data, reload } = useLoad(() => {
    let query = supabase.from('profiles').select('*').order('role').order('full_name')
    query = filter === 'staff' ? query.neq('role', 'customer') : query.eq('role', 'customer')
    return q(query)
  }, [filter])
  const setStatus = (p, status) => run(async () => { await adminUsers({ action: 'set_status', user_id: p.id, status }); reload() }, status === 'active' ? 'Reactivated.' : 'Deactivated. They can no longer sign in.')
  const reset = (p) => run(async () => { const r = await adminUsers({ action: 'reset_password', user_id: p.id }); setSecret({ email: p.email, password: r.temp_password }) })
  return (
    <>
      <PageHead title="Users & roles" sub="Internal accounts get a temporary password and must change it at first sign-in.">
        <button className="btn primary" onClick={() => setCreate('staff')}>New staff account</button>
        <button className="btn" onClick={() => setCreate('customer')}>New customer account</button>
      </PageHead>
      <div className="tabs">{[['staff', 'Staff'], ['customer', 'Customer logins']].map(([k, l]) => <button key={k} className={filter === k ? 'on' : ''} onClick={() => setFilter(k)}>{l}</button>)}</div>
      <Card pad={false}>
        {!data ? <Loading /> : (
          <div className="table-wrap"><table>
            <thead><tr><th>Name</th><th>Role</th><th>Status</th><th>Last sign-in</th><th /></tr></thead>
            <tbody>{data.map((p) => (
              <tr key={p.id}>
                <td><strong>{p.full_name || '—'}</strong><div className="muted small">{p.email}</div></td>
                <td>{ROLE_LABEL[p.role]}{p.must_change_password && <div><Badge tone="warn">Temporary password</Badge></div>}</td>
                <td><Badge tone={p.status === 'active' ? 'good' : 'muted'}>{p.status}</Badge></td>
                <td className="muted">{p.last_login ? ago(p.last_login) : 'never'}</td>
                <td className="row" style={{ justifyContent: 'flex-end' }}>
                  {p.id !== user.id && <>
                    <button className="btn sm" disabled={busy} onClick={() => reset(p)}>Reset password</button>
                    {p.status === 'active' ? <button className="btn sm danger" disabled={busy} onClick={() => setStatus(p, 'inactive')}>Deactivate</button>
                      : <button className="btn sm" disabled={busy} onClick={() => setStatus(p, 'active')}>Reactivate</button>}
                  </>}
                </td>
              </tr>
            ))}</tbody>
          </table></div>
        )}
      </Card>
      {create && <CreateUserModal kind={create} onClose={() => setCreate(null)} onDone={(r) => { setCreate(null); setSecret({ email: r.email, password: r.temp_password }); reload() }} />}
      {secret && (
        <Modal title="Temporary password" onClose={() => setSecret(null)} footer={<button className="btn primary" onClick={() => setSecret(null)}>Done</button>}>
          <p>Give this to <strong>{secret.email}</strong> privately. It is shown only once; they must change it when they first sign in.</p>
          <div className="code-box" style={{ fontSize: 20, letterSpacing: '.08em' }}>{secret.password}</div>
          <button className="btn" onClick={() => { navigator.clipboard.writeText(secret.password); toast.success('Copied.') }}>Copy</button>
        </Modal>
      )}
    </>
  )
}

function CreateUserModal({ kind, onClose, onDone }) {
  const [f, setF] = useState({ email: '', full_name: '', role: 'ops', phone: '', licence_no: '', name: '', reg_no: '', address: '', industry: '' })
  const [run, busy] = useAction()
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const submit = () => run(async () => {
    const r = kind === 'staff'
      ? await adminUsers({ action: 'create_staff', email: f.email, full_name: f.full_name, role: f.role, phone: f.phone, licence_no: f.licence_no })
      : await adminUsers({ action: 'create_customer', email: f.email, customer: { name: f.name, reg_no: f.reg_no, contact_name: f.full_name, phone: f.phone, address: f.address, industry: f.industry } })
    onDone(r)
  })
  return (
    <Modal title={kind === 'staff' ? 'New staff account' : 'New customer account'} onClose={onClose} footer={<>
      <button className="btn" onClick={onClose}>Cancel</button>
      <button className="btn primary" disabled={busy || !f.email || !f.full_name} onClick={submit}>{busy ? 'Creating…' : 'Create'}</button>
    </>}>
      {kind === 'customer' && <>
        <p className="muted">For a known client. The account is active straight away; no review step.</p>
        <label className="field">Company name<input value={f.name} onChange={set('name')} /></label>
        <label className="field">Registration number<input value={f.reg_no} onChange={set('reg_no')} /></label>
        <label className="field">Business address<input value={f.address} onChange={set('address')} /></label>
      </>}
      <label className="field">{kind === 'staff' ? 'Full name' : 'Contact person'}<input value={f.full_name} onChange={set('full_name')} /></label>
      <label className="field">E-mail (username)<input type="email" value={f.email} onChange={set('email')} /></label>
      <label className="field">Phone<input value={f.phone} onChange={set('phone')} /></label>
      {kind === 'staff' && (
        <label className="field">Role
          <select value={f.role} onChange={set('role')}>
            {['ops', 'finance', 'warehouse', 'dispatch', 'driver', 'admin'].map((r) => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}
          </select>
        </label>
      )}
      {f.role === 'driver' && kind === 'staff' && <label className="field">Driving licence no.<input value={f.licence_no} onChange={set('licence_no')} /></label>}
    </Modal>
  )
}

export function AdminCustomers() {
  const [edit, setEdit] = useState(null)
  const [status, setStatus] = useState(null)
  const { data, reload } = useLoad(async () => {
    const [cust, regions] = await Promise.all([
      q(supabase.from('customers').select('*').not('status', 'in', '(awaiting_review)').order('name')),
      q(supabase.from('regions').select('*').order('name')),
    ])
    return { cust, regions }
  })
  if (!data) return <Loading />
  return (
    <>
      <PageHead title="Customers" sub="Payment terms, regions and account status." />
      <Card pad={false}>
        <div className="table-wrap"><table>
          <thead><tr><th>Company</th><th>Status</th><th>Terms</th><th>Regions</th><th /></tr></thead>
          <tbody>{data.cust.map((c) => (
            <tr key={c.id}>
              <td><strong>{c.name}</strong>{c.trusted && <> <Badge tone="info">trusted</Badge></>}<div className="muted small">{c.reg_no} · {c.email}</div></td>
              <td><Badge tone={CUSTOMER_TONE[c.status]}>{c.status.replace('_', ' ')}</Badge></td>
              <td>{c.payment_terms}</td>
              <td className="small">{c.allowed_region_ids?.length ? data.regions.filter((r) => c.allowed_region_ids.includes(r.id)).map((r) => r.name).join(', ') : 'All'}</td>
              <td className="row" style={{ justifyContent: 'flex-end' }}>
                <button className="btn sm" onClick={() => setEdit(c)}>Terms</button>
                {c.status === 'active' ? <button className="btn sm danger" onClick={() => setStatus({ c, to: 'on_hold' })}>Hold</button>
                  : ['on_hold', 'blocked'].includes(c.status) && <button className="btn sm" onClick={() => setStatus({ c, to: 'active' })}>Reactivate</button>}
                {c.status !== 'blocked' && <button className="btn sm danger" onClick={() => setStatus({ c, to: 'blocked' })}>Block</button>}
              </td>
            </tr>
          ))}</tbody>
        </table></div>
      </Card>
      {edit && <TermsModal c={edit} regions={data.regions} onClose={() => setEdit(null)} onDone={() => { setEdit(null); reload() }} />}
      {status && <ReasonModal title={`${status.to === 'active' ? 'Reactivate' : status.to === 'blocked' ? 'Block' : 'Hold'} ${status.c.name}`} label="Reason (the customer sees this)" danger={status.to !== 'active'}
        onClose={() => setStatus(null)} onSubmit={async (r) => { await rpc('set_customer_status', { p_customer: status.c.id, p_status: status.to, p_note: r }); reload() }} />}
    </>
  )
}

function TermsModal({ c, regions, onClose, onDone }) {
  const [t, setT] = useState({ payment_terms: c.payment_terms, credit_limit: c.credit_limit, allowed_region_ids: c.allowed_region_ids || [], trusted: c.trusted })
  const [run, busy] = useAction()
  return (
    <Modal title={`Terms for ${c.name}`} onClose={onClose} footer={<>
      <button className="btn" onClick={onClose}>Cancel</button>
      <button className="btn primary" disabled={busy} onClick={() => run(async () => { await rpc('update_customer_terms', { p_customer: c.id, p_terms: { ...t, credit_limit: Number(t.credit_limit) } }); onDone() }, 'Saved.')}>Save</button>
    </>}>
      <TermsFields t={t} setT={setT} regions={regions} />
    </Modal>
  )
}

export function AdminCatalogue() {
  const [edit, setEdit] = useState(null)
  const { data, reload } = useLoad(() => q(supabase.from('products').select('*').order('name')))
  return (
    <>
      <PageHead title="Catalogue & prices" sub="Stock quantities belong to the warehouse; prices and limits belong to you.">
        <button className="btn primary" onClick={() => setEdit({ unit: 'unit', min_qty: 1, max_qty: 1000, reorder_level: 0, active: true })}>Add product</button>
      </PageHead>
      <Card pad={false}>
        {!data ? <Loading /> : (
          <div className="table-wrap"><table>
            <thead><tr><th>Product</th><th className="num">Price</th><th>Limits</th><th className="num">Reorder level</th><th className="num">Available</th><th>Status</th><th /></tr></thead>
            <tbody>{data.map((p) => (
              <tr key={p.id}><td><strong>{p.name}</strong><div className="muted mono">{p.sku} · per {p.unit}</div></td><td className="num">{money(p.price)}</td>
                <td className="muted">{p.min_qty}–{p.max_qty}</td><td className="num">{p.reorder_level}</td><td className="num">{p.on_hand - p.reserved}</td>
                <td>{!p.active && Number(p.price) === 0 ? <Badge tone="warn">Needs a price</Badge> : <Badge tone={p.active ? 'good' : 'muted'}>{p.active ? 'active' : 'inactive'}</Badge>}</td>
                <td><button className="btn sm" onClick={() => setEdit(p)}>Edit</button></td></tr>
            ))}</tbody>
          </table></div>
        )}
      </Card>
      {edit && <ProductModal p={edit} onClose={() => setEdit(null)} onDone={() => { setEdit(null); reload() }} />}
    </>
  )
}

function ProductModal({ p, onClose, onDone }) {
  const [f, setF] = useState({ sku: p.sku || '', name: p.name || '', unit: p.unit, price: p.price ?? '', min_qty: p.min_qty, max_qty: p.max_qty, reorder_level: p.reorder_level, active: p.active })
  const [run, busy] = useAction()
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const save = () => run(async () => {
    const row = { ...f, sku: f.sku.trim().toUpperCase(), price: Number(f.price), min_qty: Number(f.min_qty), max_qty: Number(f.max_qty), reorder_level: Number(f.reorder_level) }
    if (!row.sku || !row.name || !(row.price >= 0)) throw new Error('SKU, name and price are required.')
    if (row.min_qty < 1 || row.max_qty < row.min_qty) throw new Error('Check the order limits.')
    if (row.active && !(row.price > 0)) throw new Error('Set a price above 0 before activating the product.')
    await q(p.id ? supabase.from('products').update(row).eq('id', p.id).select() : supabase.from('products').insert(row).select())
    onDone()
  }, 'Saved.')
  return (
    <Modal title={p.id ? `Edit ${p.sku}` : 'Add product'} onClose={onClose} footer={<>
      <button className="btn" onClick={onClose}>Cancel</button><button className="btn primary" disabled={busy} onClick={save}>Save</button>
    </>}>
      <div className="form-grid">
        <label className="field">SKU<input value={f.sku} onChange={set('sku')} disabled={!!p.id} /></label>
        <label className="field">Unit<input value={f.unit} onChange={set('unit')} /></label>
        <label className="field full">Name<input value={f.name} onChange={set('name')} /></label>
        <label className="field">Price (₦)<input type="number" step="0.01" value={f.price} onChange={set('price')} /></label>
        <label className="field">Reorder level<input type="number" value={f.reorder_level} onChange={set('reorder_level')} /></label>
        <label className="field">Minimum per order<input type="number" value={f.min_qty} onChange={set('min_qty')} /></label>
        <label className="field">Maximum per order<input type="number" value={f.max_qty} onChange={set('max_qty')} /></label>
        <label className="row full"><input type="checkbox" checked={f.active} onChange={(e) => setF({ ...f, active: e.target.checked })} /> Active (customers can order it)</label>
      </div>
      {p.id && Number(f.price) !== Number(p.price) && <div className="notice warn">Drafts with the old price will fail the pricing check until the customer saves them again.</div>}
    </Modal>
  )
}

export function AdminRegions() {
  const [run, busy] = useAction()
  const [f, setF] = useState({ name: '', delivery_fee: '' })
  const { data, reload } = useLoad(() => q(supabase.from('regions').select('*').order('name')))
  const save = (r, patch) => run(async () => { await q(supabase.from('regions').update(patch).eq('id', r.id).select()); reload() }, 'Saved.')
  return (
    <>
      <PageHead title="Regions & delivery fees" sub="A flat delivery fee per region; tax is set in Rules." />
      <Card pad={false}>
        {!data ? <Loading /> : (
          <div className="table-wrap"><table>
            <thead><tr><th>Region</th><th style={{ width: 200 }}>Delivery fee (₦)</th><th>Status</th><th /></tr></thead>
            <tbody>{data.map((r) => (
              <tr key={r.id}><td>{r.name}</td>
                <td><input type="number" defaultValue={r.delivery_fee} onBlur={(e) => Number(e.target.value) !== Number(r.delivery_fee) && save(r, { delivery_fee: Number(e.target.value) })} /></td>
                <td><Badge tone={r.active ? 'good' : 'muted'}>{r.active ? 'active' : 'inactive'}</Badge></td>
                <td><button className="btn sm" disabled={busy} onClick={() => save(r, { active: !r.active })}>{r.active ? 'Deactivate' : 'Activate'}</button></td></tr>
            ))}</tbody>
          </table></div>
        )}
        <div className="card-body row">
          <input placeholder="New region" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} style={{ width: 220 }} />
          <input placeholder="Fee" type="number" value={f.delivery_fee} onChange={(e) => setF({ ...f, delivery_fee: e.target.value })} style={{ width: 140 }} />
          <button className="btn primary" disabled={!f.name.trim() || busy} onClick={() => run(async () => { await q(supabase.from('regions').insert({ name: f.name.trim(), delivery_fee: Number(f.delivery_fee || 0) }).select()); setF({ name: '', delivery_fee: '' }); reload() }, 'Added.')}>Add</button>
        </div>
      </Card>
    </>
  )
}

const SETTING_GROUPS = [
  ['Orders and validation', ['duplicate_window_hours', 'price_tolerance', 'unusual_qty_factor', 'low_stock_warn_qty', 'auto_approve_enabled', 'auto_approve_max_total', 'stuck_order_hours']],
  ['Payment', ['tax_rate', 'payment_window_hours', 'payment_reupload_grace_hours', 'max_payment_attempts', 'bank_details']],
  ['Delivery and shortages', ['delivery_code_max_attempts', 'delivery_code_valid_days', 'restock_wait_days']],
  ['Onboarding', ['require_documents', 'reject_free_domains', 'manual_review_volume', 'reapply_wait_days', 'default_payment_terms', 'default_credit_limit']],
]

export function Rules() {
  const [run, busy] = useAction()
  const [vals, setVals] = useState({})
  const [entry, setEntry] = useState({ kind: 'blocked_reg_no', value: '', note: '' })
  const { data, reload } = useLoad(async () => {
    const [settings, lists] = await Promise.all([q(supabase.from('settings').select('*')), q(supabase.from('screening_list').select('*').order('kind'))])
    return { settings: Object.fromEntries(settings.map((s) => [s.key, s])), lists }
  })
  if (!data) return <Loading />
  const saveKey = (key) => run(async () => {
    const s = data.settings[key]
    let v = vals[key]
    try { v = JSON.parse(v) } catch { if (typeof s.value === 'string') v = String(v); else throw new Error('Enter a valid value.') }
    if (typeof s.value !== typeof v) throw new Error(`Expected a ${typeof s.value}.`)
    await q(supabase.from('settings').update({ value: v }).eq('key', key).select())
    setVals({ ...vals, [key]: undefined }); reload()
  }, 'Saved.')
  const show = (v) => (typeof v === 'string' ? JSON.stringify(v) : JSON.stringify(v))
  return (
    <>
      <PageHead title="Rules & settings" sub="Every change is logged in the audit trail." />
      {SETTING_GROUPS.map(([title, keys]) => (
        <Card key={title} title={title} pad={false}>
          <div className="table-wrap"><table><tbody>{keys.filter((k) => data.settings[k]).map((k) => {
            const s = data.settings[k]
            const isBool = typeof s.value === 'boolean'
            return (
              <tr key={k}>
                <td style={{ width: '45%' }}><strong>{k.replace(/_/g, ' ')}</strong><div className="muted small">{s.description}</div></td>
                <td>{isBool ? (
                  <label className="row"><input type="checkbox" checked={s.value} disabled={busy} onChange={(e) => run(async () => { await q(supabase.from('settings').update({ value: e.target.checked }).eq('key', k).select()); reload() }, 'Saved.')} /> {s.value ? 'On' : 'Off'}</label>
                ) : (
                  <div className="row" style={{ flexWrap: 'nowrap' }}>
                    <input className={typeof s.value === 'object' ? 'mono' : ''} value={vals[k] ?? show(s.value)} onChange={(e) => setVals({ ...vals, [k]: e.target.value })} />
                    {vals[k] !== undefined && <button className="btn sm primary" disabled={busy} onClick={() => saveKey(k)}>Save</button>}
                  </div>
                )}</td>
              </tr>
            )
          })}</tbody></table></div>
        </Card>
      ))}
      <Card title="Screening lists" pad={false}>
        <div className="table-wrap"><table>
          <thead><tr><th>List</th><th>Value</th><th>Note</th><th /></tr></thead>
          <tbody>{data.lists.map((l) => (
            <tr key={l.id}><td><Badge tone={l.kind.startsWith('blocked') ? 'bad' : l.kind === 'preapproved_reg_no' ? 'good' : 'warn'}>{l.kind.replace(/_/g, ' ')}</Badge></td><td className="mono">{l.value}</td><td className="muted">{l.note}</td>
              <td><button className="btn sm" disabled={busy} onClick={() => run(async () => { await q(supabase.from('screening_list').delete().eq('id', l.id).select()); reload() }, 'Removed.')}>Remove</button></td></tr>
          ))}</tbody>
        </table></div>
        <div className="card-body row">
          <select value={entry.kind} onChange={(e) => setEntry({ ...entry, kind: e.target.value })} style={{ width: 220 }}>
            {['blocked_reg_no', 'blocked_email', 'blocked_domain', 'free_domain', 'preapproved_reg_no'].map((k) => <option key={k} value={k}>{k.replace(/_/g, ' ')}</option>)}
          </select>
          <input placeholder="Value" value={entry.value} onChange={(e) => setEntry({ ...entry, value: e.target.value })} style={{ width: 220 }} />
          <input placeholder="Note" value={entry.note} onChange={(e) => setEntry({ ...entry, note: e.target.value })} style={{ width: 220 }} />
          <button className="btn primary" disabled={!entry.value.trim() || busy} onClick={() => run(async () => { await q(supabase.from('screening_list').insert({ ...entry, value: entry.value.trim().toLowerCase() }).select()); setEntry({ ...entry, value: '', note: '' }); reload() }, 'Added.')}>Add</button>
        </div>
      </Card>
    </>
  )
}

export function AuditLog() {
  const [entity, setEntity] = useState('')
  const [s, setS] = useState('')
  const { data } = useLoad(async () => {
    let query = supabase.from('audit_log').select('*').order('at', { ascending: false }).limit(300)
    if (entity) query = query.eq('entity', entity)
    if (s.trim()) query = query.ilike('action', `%${s.trim()}%`)
    const rows = await q(query)
    const ids = [...new Set(rows.map((r) => r.user_id).filter(Boolean))]
    const people = ids.length ? await q(supabase.from('profiles').select('id,full_name,role').in('id', ids)) : []
    return { rows, people: Object.fromEntries(people.map((p) => [p.id, p])) }
  }, [entity, s])
  return (
    <>
      <PageHead title="Audit log" sub="Who did what and when. Entries cannot be edited from the application." />
      <div className="row">
        <select value={entity} onChange={(e) => setEntity(e.target.value)} style={{ width: 200 }}>
          <option value="">All entities</option>
          {['order', 'payment', 'refund', 'customer', 'product', 'products', 'delivery', 'delivery_code', 'settings', 'regions', 'user', 'profiles', 'screening_list', 'vehicles'].map((x) => <option key={x}>{x}</option>)}
        </select>
        <input placeholder="Action contains…" value={s} onChange={(e) => setS(e.target.value)} style={{ width: 220 }} />
      </div>
      <Card pad={false}>
        {!data ? <Loading /> : (
          <div className="table-wrap"><table>
            <thead><tr><th>When</th><th>Who</th><th>Entity</th><th>Action</th><th>Change</th></tr></thead>
            <tbody>{data.rows.map((r) => (
              <tr key={r.id}>
                <td className="nowrap">{dateTime(r.at)}</td>
                <td>{data.people[r.user_id]?.full_name || (r.user_id ? '—' : 'system')}<div className="muted small">{ROLE_LABEL[data.people[r.user_id]?.role] || ''}</div></td>
                <td>{r.entity}</td>
                <td><strong>{r.action}</strong>{r.action === 'override' && <> <Badge tone="bad">override</Badge></>}</td>
                <td className="mono small" style={{ maxWidth: 420, wordBreak: 'break-word' }}>{summarise(r)}</td>
              </tr>
            ))}</tbody>
          </table></div>
        )}
      </Card>
    </>
  )
}

function summarise(r) {
  const o = r.old_value || {}
  const n = r.new_value || {}
  if (r.action === 'status_change' && n.status) return `${o.status || '—'} → ${n.status}${n.note ? ` (${n.note})` : ''}`
  if (r.action === 'update' && r.old_value && r.new_value) {
    const keys = Object.keys(n).filter((k) => JSON.stringify(o[k]) !== JSON.stringify(n[k]))
    return keys.map((k) => `${k}: ${JSON.stringify(o[k])} → ${JSON.stringify(n[k])}`).join('; ')
  }
  return JSON.stringify(r.new_value || r.old_value || {}).slice(0, 300)
}

export { date, ACTIVE_STATUSES }
