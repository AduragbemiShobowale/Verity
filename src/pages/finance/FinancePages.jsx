import { useState } from 'react'
import { Link } from 'react-router-dom'
import { supabase, rpc, signedUrl } from '../../lib/supabase'
import { money, dateTime, ago, hoursLeft } from '../../lib/format'
import { Card, PageHead, Kpi, Badge, Empty, Loading, ReasonModal, useLoad, q, countOf, useAction } from '../../components/ui'

const head = () => ({ count: 'exact', head: true })

export function FinanceDashboard() {
  const { data } = useLoad(async () => {
    const today = new Date(); today.setHours(0, 0, 0, 0)
    const [toVerify, confirmedToday, rejected, refunds, recent] = await Promise.all([
      countOf(supabase.from('payments').select('id', head()).eq('status', 'pending')),
      countOf(supabase.from('payments').select('id', head()).eq('status', 'confirmed').gte('verified_at', today.toISOString())),
      countOf(supabase.from('payments').select('id', head()).eq('status', 'rejected').gte('verified_at', today.toISOString())),
      countOf(supabase.from('refunds').select('id', head()).eq('status', 'requested')),
      q(supabase.from('payments').select('*, invoices(invoice_no,total,order_id), customers(name)').order('created_at', { ascending: false }).limit(10)),
    ])
    return { toVerify, confirmedToday, rejected, refunds, recent }
  })
  return (
    <>
      <PageHead title="Finance" sub="Match uploaded proofs against the bank statement, and pay refunds." />
      <div className="kpis">
        <Kpi label="Payments to verify" value={data?.toVerify} to="/finance/payments" alert={data?.toVerify > 0} />
        <Kpi label="Confirmed today" value={data?.confirmedToday} />
        <Kpi label="Rejected proofs today" value={data?.rejected} />
        <Kpi label="Refunds pending" value={data?.refunds} to="/finance/refunds" alert={data?.refunds > 0} />
      </div>
      <Card title="Recent payments" pad={false}>
        {!data ? <Loading /> : data.recent.length === 0 ? <Empty>No payments yet.</Empty> : (
          <div className="table-wrap"><table>
            <thead><tr><th>Invoice</th><th>Customer</th><th>Reference</th><th>Uploaded</th><th>Status</th><th className="num">Amount</th></tr></thead>
            <tbody>{data.recent.map((p) => (
              <tr key={p.id}><td>{p.invoices?.invoice_no}</td><td>{p.customers?.name}</td><td className="mono">{p.reference}</td><td>{ago(p.created_at)}</td>
                <td><Badge tone={p.status === 'confirmed' ? 'good' : p.status === 'rejected' ? 'bad' : 'warn'}>{p.status}</Badge></td><td className="num">{money(p.amount)}</td></tr>
            ))}</tbody>
          </table></div>
        )}
      </Card>
    </>
  )
}

export function PaymentsToVerify() {
  const [sel, setSel] = useState(null)
  const [reject, setReject] = useState(false)
  const [proofUrl, setProofUrl] = useState(null)
  const [run, busy] = useAction()
  const { data, reload } = useLoad(() => q(supabase.from('payments').select('*, invoices(*, orders(order_no)), customers(name)').eq('status', 'pending').order('created_at')))
  const cur = data?.find((p) => p.id === sel) || data?.[0]
  const showProof = async (p) => {
    setProofUrl(null)
    if (p.proof_path) setProofUrl({ url: await signedUrl('payment-proofs', p.proof_path), pdf: /\.pdf$/i.test(p.proof_path) })
  }
  const diff = cur ? Number(cur.amount) - Number(cur.invoices.total) : 0
  return (
    <>
      <PageHead title="Payments to verify" sub="Confirm only when the amount and reference appear on the bank statement." />
      {!data ? <Loading /> : data.length === 0 ? <Card><Empty>No payments waiting.</Empty></Card> : (
        <div className="grid-main" style={{ gridTemplateColumns: 'minmax(0,1fr) minmax(0,1.4fr)' }}>
          <Card pad={false}>
            <div className="table-wrap"><table>
              <tbody>{data.map((p) => (
                <tr key={p.id} className={`click ${cur?.id === p.id ? 'selected' : ''}`} onClick={() => { setSel(p.id); setProofUrl(null) }}>
                  <td><strong>{p.invoices.invoice_no}</strong><div className="muted small">{p.customers?.name}</div></td>
                  <td className="mono small">{p.reference}<div className="muted">{ago(p.created_at)}</div></td>
                  <td className="num">{money(p.amount)}</td>
                </tr>
              ))}</tbody>
            </table></div>
          </Card>
          {cur && (
            <Card title={`${cur.invoices.invoice_no} · ${cur.invoices.orders?.order_no}`} action={<Link to={'/order/' + cur.invoices.order_id}>Order</Link>}>
              <div className="stack-lg">
                <div className="grid-2">
                  <div className="card card-pad" style={{ boxShadow: 'none' }}><div className="muted small">Invoice total</div><div style={{ fontSize: 22, fontWeight: 700 }}>{money(cur.invoices.total)}</div></div>
                  <div className="card card-pad" style={{ boxShadow: 'none', borderColor: diff ? 'var(--bad)' : 'var(--good)' }}><div className="muted small">Amount on proof</div><div style={{ fontSize: 22, fontWeight: 700, color: diff ? 'var(--bad)' : 'var(--good)' }}>{money(cur.amount)}</div></div>
                </div>
                {diff !== 0 && <div className="notice bad">The amount is {money(Math.abs(diff))} {diff < 0 ? 'short' : 'over'}.</div>}
                <div className="stack">
                  <div className="row between"><span className="muted">Customer</span><span>{cur.customers?.name}</span></div>
                  <div className="row between"><span className="muted">Reference</span><span className="mono">{cur.reference}</span></div>
                  <div className="row between"><span className="muted">Attempt</span><span>{cur.attempt_no}</span></div>
                  <div className="row between"><span className="muted">Uploaded</span><span>{dateTime(cur.created_at)}</span></div>
                </div>
                {cur.proof_path ? (proofUrl ? (proofUrl.pdf ? <iframe title="Proof" src={proofUrl.url} style={{ width: '100%', height: 360, border: '1px solid var(--line)', borderRadius: 8 }} />
                  : <img alt="Payment proof" src={proofUrl.url} style={{ maxWidth: '100%', borderRadius: 8, border: '1px solid var(--line)' }} />)
                  : <button className="btn" onClick={() => showProof(cur)}>View proof</button>) : <p className="muted">No file; reference only.</p>}
                <div className="row">
                  <button className="btn primary lg" disabled={busy} onClick={() => run(async () => { await rpc('confirm_payment', { p_payment: cur.id }); setSel(null); reload() }, 'Payment confirmed. Order sent to the warehouse.')}>Confirm payment</button>
                  <button className="btn danger lg" onClick={() => setReject(true)}>Reject</button>
                </div>
              </div>
            </Card>
          )}
        </div>
      )}
      {reject && cur && <ReasonModal title="Reject payment proof" label="Reason (the customer sees this)" danger confirm="Reject"
        options={['Amount does not match the invoice', 'Reference not found on the bank statement', 'Proof is unreadable', 'Payment is for a different invoice']}
        onClose={() => setReject(false)} onSubmit={async (r) => { await rpc('reject_payment', { p_payment: cur.id, p_reason: r }); setSel(null); reload() }} />}
    </>
  )
}

export function FinanceRefunds() {
  const [pay, setPay] = useState(null)
  const [tab, setTab] = useState('requested')
  const { data, reload } = useLoad(() => q(supabase.from('refunds').select('*, orders(order_no), customers(name)').eq('status', tab).order('requested_at', { ascending: tab === 'requested' }).limit(200)), [tab])
  return (
    <>
      <PageHead title="Refunds" sub="Pay the refund by transfer, then record the reference. A credit note is issued automatically." />
      <div className="tabs">{[['requested', 'To pay'], ['paid', 'Paid']].map(([k, l]) => <button key={k} className={tab === k ? 'on' : ''} onClick={() => setTab(k)}>{l}</button>)}</div>
      <Card pad={false}>
        {!data ? <Loading /> : data.length === 0 ? <Empty>None.</Empty> : (
          <div className="table-wrap"><table>
            <thead><tr><th>Order</th><th>Customer</th><th>Reason</th><th>{tab === 'paid' ? 'Paid' : 'Requested'}</th><th className="num">Amount</th><th /></tr></thead>
            <tbody>{data.map((r) => (
              <tr key={r.id}><td><Link to={'/order/' + r.order_id}>{r.orders?.order_no}</Link></td><td>{r.customers?.name}</td><td>{r.reason}</td>
                <td>{dateTime(r.paid_at || r.requested_at)}{r.credit_note_no && <div className="muted small">{r.credit_note_no} · ref {r.reference}</div>}</td>
                <td className="num"><strong>{money(r.amount)}</strong></td>
                <td>{r.status === 'requested' && <button className="btn primary sm" onClick={() => setPay(r)}>Mark paid</button>}</td></tr>
            ))}</tbody>
          </table></div>
        )}
      </Card>
      {pay && <ReasonModal title={`Refund ${money(pay.amount)} to ${pay.customers?.name}`} label="Transfer reference" confirm="Record payment"
        onClose={() => setPay(null)} onSubmit={async (ref) => { await rpc('mark_refund_paid', { p_refund: pay.id, p_reference: ref }); reload() }} />}
    </>
  )
}

export function FinanceInvoices() {
  const [status, setStatus] = useState('issued')
  const { data } = useLoad(() => q(supabase.from('invoices').select('*, orders(order_no,status), customers(name)').eq('status', status).order('created_at', { ascending: false }).limit(300)), [status])
  return (
    <>
      <PageHead title="Invoices" />
      <div className="tabs">{['issued', 'paid', 'expired', 'credited', 'cancelled'].map((s) => <button key={s} className={status === s ? 'on' : ''} onClick={() => setStatus(s)}>{s}</button>)}</div>
      <Card pad={false}>
        {!data ? <Loading /> : data.length === 0 ? <Empty>None.</Empty> : (
          <div className="table-wrap"><table>
            <thead><tr><th>Invoice</th><th>Order</th><th>Customer</th><th>Due</th><th className="num">Total</th></tr></thead>
            <tbody>{data.map((i) => (
              <tr key={i.id}><td>{i.invoice_no}</td><td><Link to={'/order/' + i.order_id}>{i.orders?.order_no}</Link></td><td>{i.customers?.name}</td>
                <td>{dateTime(i.due_at)}{status === 'issued' && <div className="muted small">{hoursLeft(i.due_at)}</div>}</td><td className="num">{money(i.total)}</td></tr>
            ))}</tbody>
          </table></div>
        )}
      </Card>
    </>
  )
}
