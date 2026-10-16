import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useSearchParams, Link } from 'react-router-dom'
import toast from 'react-hot-toast'
import readXlsxFile from 'read-excel-file'
import { supabase, rpc } from '../../lib/supabase'
import { money, tomorrow } from '../../lib/format'
import { rowsToOrder, parseCsv, textToRows } from '../../lib/upload'
import { Card, PageHead, Modal, ValidationReport, Loading, Badge, Empty } from '../../components/ui'

const stockBadge = (p) =>
  p.stock_status === 'out_of_stock' ? <Badge tone="bad">Out of stock</Badge>
    : p.stock_status === 'low_stock' ? <Badge tone="warn">Only {p.only_left} left</Badge>
      : <Badge tone="good">In stock</Badge>

export default function NewOrder() {
  const nav = useNavigate()
  const [params] = useSearchParams()
  const editId = params.get('edit')
  const [ref, setRef] = useState(null)
  const [orderId, setOrderId] = useState(editId)
  const [lines, setLines] = useState([]) // {product_id, qty}
  const [unmatched, setUnmatched] = useState([])
  const [notes, setNotes] = useState([])
  const [addressId, setAddressId] = useState('')
  const [reqDate, setReqDate] = useState(tomorrow())
  const [orderNotes, setOrderNotes] = useState('')
  const [source, setSource] = useState('portal')
  const [search, setSearch] = useState('')
  const [report, setReport] = useState(null)
  const [checking, setChecking] = useState(false)
  const [busy, setBusy] = useState(false)
  const [dup, setDup] = useState(null)
  const [paste, setPaste] = useState(false)
  const [pasteText, setPasteText] = useState('')
  const dirty = useRef(0)

  useEffect(() => {
    (async () => {
      const [cat, addr, regions, tax] = await Promise.all([
        rpc('get_catalogue'),
        supabase.from('addresses').select('*').eq('active', true).order('label'),
        supabase.from('regions').select('*'),
        supabase.from('settings').select('value').eq('key', 'tax_rate').single(),
      ])
      setRef({ catalogue: cat, addresses: addr.data || [], regions: regions.data || [], tax: Number(tax.data?.value || 0) })
      if (!editId && addr.data?.length) setAddressId(addr.data[0].id)
      if (editId) {
        const { data: o } = await supabase.from('orders').select('*, order_items(*)').eq('id', editId).single()
        if (o) {
          setLines(o.order_items.filter((i) => i.qty_ordered > 0).map((i) => ({ product_id: i.product_id, qty: i.qty_ordered })))
          setUnmatched(o.unmatched_lines || [])
          setAddressId(o.address_id || '')
          setReqDate(o.requested_date || tomorrow())
          setOrderNotes(o.notes || '')
          setSource(o.source)
          const { data: vr } = await supabase.from('validation_results').select('*').eq('order_id', editId).eq('current', true).order('id')
          if (vr?.length && o.status !== 'draft') setReport({ outcome: o.validation_outcome, results: vr })
        }
      }
    })().catch((e) => toast.error(e.message))
  }, [editId])

  const byId = useMemo(() => Object.fromEntries((ref?.catalogue || []).map((p) => [p.id, p])), [ref])
  const address = ref?.addresses.find((a) => a.id === addressId)
  const fee = Number(ref?.regions.find((r) => r.id === address?.region_id)?.delivery_fee || 0)
  const subtotal = lines.reduce((s, l) => s + (byId[l.product_id]?.price || 0) * (Number(l.qty) || 0), 0)
  const tax = Math.round((subtotal + fee) * (ref?.tax || 0)) / 100
  const total = subtotal + fee + tax

  const payload = () => ({
    address_id: addressId || null, requested_date: reqDate || null, notes: orderNotes, source,
    items: lines.map((l) => ({ product_id: l.product_id, qty: l.qty === '' ? null : Number(l.qty) })),
    unmatched,
  })

  const save = async () => {
    const id = await rpc('save_draft', { p_order: orderId, p: payload() })
    setOrderId(id)
    return id
  }

  // server-side check a moment after the customer stops editing
  useEffect(() => {
    if (!ref || (!lines.length && !unmatched.length)) return
    const n = ++dirty.current
    const t = setTimeout(async () => {
      setChecking(true)
      try {
        const id = await save()
        const r = await rpc('check_order', { p_order: id })
        if (n === dirty.current) setReport(r)
      } catch (e) {
        if (n === dirty.current) toast.error(e.message)
      } finally {
        setChecking(false)
      }
    }, 1200)
    return () => clearTimeout(t)
  }, [lines, unmatched, addressId, reqDate]) // eslint-disable-line react-hooks/exhaustive-deps

  const add = (p) => {
    if (lines.some((l) => l.product_id === p.id)) return toast('Already on the order. Change the quantity instead.')
    setLines([...lines, { product_id: p.id, qty: p.min_qty }])
    setSearch('')
  }
  const setQty = (id, qty) => setLines(lines.map((l) => (l.product_id === id ? { ...l, qty } : l)))
  const remove = (id) => setLines(lines.filter((l) => l.product_id !== id))

  const applyRows = (rows, kind) => {
    const out = rowsToOrder(rows, ref.catalogue)
    if (out.error) return toast.error(out.error)
    const merged = new Map(lines.map((l) => [l.product_id, l]))
    for (const it of out.items) merged.set(it.product_id, { product_id: it.product_id, qty: (Number(merged.get(it.product_id)?.qty) || 0) + it.qty })
    setLines([...merged.values()])
    setUnmatched([...unmatched, ...out.unmatched])
    setNotes(out.notes || [])
    setSource('upload')
    toast.success(`${out.items.length} line(s) read from the ${kind}${out.unmatched.length ? `, ${out.unmatched.length} need attention` : ''}.`)
  }

  const onFile = async (e) => {
    const file = e.target.files[0]
    e.target.value = ''
    if (!file) return
    try {
      if (/\.xlsx$/i.test(file.name)) applyRows(await readXlsxFile(file), 'spreadsheet')
      else if (/\.(csv|txt)$/i.test(file.name)) applyRows(parseCsv(await file.text()), 'file')
      else toast.error('Upload an .xlsx or .csv file. For old .xls files, save as .xlsx first.')
    } catch (err) {
      toast.error('Could not read that file: ' + err.message)
    }
  }

  const submit = async (confirmDup = false) => {
    setBusy(true)
    try {
      const id = await save()
      const r = await rpc('submit_order', { p_order: id, p_confirm_duplicate: confirmDup })
      setReport(r)
      if (r.needs_confirmation) {
        setDup(r.results.find((x) => x.rule === 'duplicate')?.message)
      } else if (r.status === 'validation_failed') {
        toast.error('Fix the items marked in red, then submit again.')
      } else if (r.auto_approved) {
        toast.success('Approved. Your invoice is ready to pay.')
        nav('/invoices')
      } else {
        toast.success('Submitted for review.')
        nav('/orders/' + id)
      }
    } catch (e) {
      toast.error(e.message)
    } finally {
      setBusy(false)
    }
  }

  if (!ref) return <Loading />
  const fails = (report?.results || []).filter((r) => r.severity === 'fail')
  const failFor = (pid) => fails.filter((r) => r.field === pid)
  const matches = search.length >= 1
    ? ref.catalogue.filter((p) => (p.name + ' ' + p.sku).toLowerCase().includes(search.toLowerCase())).slice(0, 8)
    : []

  return (
    <>
      <PageHead title={editId ? 'Edit order' : 'New order'} sub="Choose products from the catalogue or upload your own order sheet. Every line is checked before you submit.">
        <label className="btn">Upload Excel / CSV<input type="file" accept=".xlsx,.csv,.txt" hidden onChange={onFile} /></label>
        <button className="btn" onClick={() => setPaste(true)}>Paste a message</button>
      </PageHead>

      {!ref.addresses.length && (
        <div className="notice warn">Add a delivery address before ordering. <Link to="/profile">Add address</Link></div>
      )}

      <div className="grid-main">
        <div className="stack-lg">
          <Card title="Items" pad={false}>
            <div className="card-body" style={{ position: 'relative' }}>
              <input placeholder="Search products by name or SKU…" value={search} onChange={(e) => setSearch(e.target.value)} />
              {matches.length > 0 && (
                <div className="card" style={{ position: 'absolute', left: 18, right: 18, top: 60, zIndex: 5 }}>
                  {matches.map((p) => (
                    <div key={p.id} className="notif" onClick={() => add(p)}>
                      <div className="row between"><strong>{p.name}</strong>{stockBadge(p)}</div>
                      <div className="muted small">{p.sku} · {money(p.price)} per {p.unit} · min {p.min_qty}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div className="table-wrap">
              <table>
                <thead><tr><th>Product</th><th>Stock</th><th className="num">Unit price</th><th style={{ width: 120 }}>Quantity</th><th className="num">Line total</th><th /></tr></thead>
                <tbody>
                  {lines.length === 0 && <tr><td colSpan={6}><Empty>No items yet. Search above or upload your sheet.</Empty></td></tr>}
                  {lines.map((l) => {
                    const p = byId[l.product_id]
                    if (!p) return null
                    const errs = failFor(l.product_id)
                    return (
                      <tr key={l.product_id}>
                        <td><strong>{p.name}</strong><div className="muted small">{p.sku}</div>
                          {errs.map((e, i) => <div key={i} className="small" style={{ color: 'var(--bad)' }}>{e.message}</div>)}
                        </td>
                        <td>{stockBadge(p)}</td>
                        <td className="num">{money(p.price)}</td>
                        <td><input className={errs.length ? 'bad' : ''} type="number" min={p.min_qty} max={p.max_qty} step="1" value={l.qty} onChange={(e) => setQty(l.product_id, e.target.value)} aria-label={`Quantity of ${p.name}`} /></td>
                        <td className="num">{money(p.price * (Number(l.qty) || 0))}</td>
                        <td><button className="btn ghost sm" onClick={() => remove(l.product_id)} aria-label={`Remove ${p.name}`}>✕</button></td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </Card>

          {unmatched.length > 0 && (
            <Card title="Lines that need attention" action={<button className="btn sm" onClick={() => setUnmatched([])}>Remove all</button>}>
              <div className="stack">
                <p className="muted">These lines from your upload could not be matched to the catalogue. Add the right product above, then remove the line.</p>
                {unmatched.map((u, i) => (
                  <div key={i} className="vr-item fail">
                    <strong>✕</strong>
                    <div className="row between">
                      <span>{u.row ? `Row ${u.row}: ` : ''}<strong>{u.sku || u.name || 'line'}</strong> {u.qty ? `× ${u.qty}` : ''} – {u.problem}</span>
                      <button className="btn sm" onClick={() => setUnmatched(unmatched.filter((_, j) => j !== i))}>Remove</button>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}
          {notes.length > 0 && <div className="notice info">{notes.map((n, i) => <div key={i}>{n}</div>)}</div>}

          <Card title="Delivery">
            <div className="form-grid">
              <label className="field">Delivery address
                <select value={addressId} onChange={(e) => setAddressId(e.target.value)} className={fails.some((r) => r.field === 'address_id') ? 'bad' : ''}>
                  <option value="">Choose…</option>
                  {ref.addresses.map((a) => <option key={a.id} value={a.id}>{a.label} – {a.line}</option>)}
                </select>
              </label>
              <label className="field">Requested delivery date
                <input type="date" min={new Date().toISOString().slice(0, 10)} value={reqDate} onChange={(e) => setReqDate(e.target.value)} className={fails.some((r) => r.field === 'requested_date') ? 'bad' : ''} />
              </label>
              <label className="field full">Notes for the warehouse or driver (optional)
                <input value={orderNotes} onChange={(e) => setOrderNotes(e.target.value)} />
              </label>
            </div>
          </Card>
        </div>

        <div className="stack-lg" style={{ position: 'sticky', top: 72 }}>
          <Card title="Invoice preview">
            <div className="totals">
              <div className="line"><span>Items ({lines.length})</span><span className="num">{money(subtotal)}</span></div>
              <div className="line"><span>Delivery fee{address ? ` (${ref.regions.find((r) => r.id === address.region_id)?.name})` : ''}</span><span className="num">{money(fee)}</span></div>
              <div className="line"><span>Tax ({ref.tax}%)</span><span className="num">{money(tax)}</span></div>
              <div className="line grand"><span>Total</span><span className="num">{money(total)}</span></div>
            </div>
            <p className="muted small" style={{ marginTop: 10 }}>You pay after the order is approved, so you are never charged for an order we cannot fulfil.</p>
          </Card>
          <Card title="Checks" action={checking ? <span className="muted small">Checking…</span> : report && <Badge tone={report.outcome === 'fail' ? 'bad' : report.outcome === 'warn' ? 'warn' : 'good'}>{report.outcome === 'fail' ? 'Fix before submitting' : report.outcome === 'warn' ? 'Passed with warnings' : 'All checks passed'}</Badge>}>
            {report ? <ValidationReport results={report.results} /> : <p className="muted">Add items to see the checks.</p>}
          </Card>
          <button className="btn primary lg block" disabled={busy || (!lines.length && !unmatched.length)} onClick={() => submit(false)}>
            {busy ? 'Submitting…' : 'Submit order'}
          </button>
        </div>
      </div>

      {dup && (
        <Modal title="Is this a new order?" onClose={() => setDup(null)} footer={<>
          <button className="btn" onClick={() => setDup(null)}>Go back</button>
          <button className="btn primary" onClick={() => { setDup(null); submit(true) }}>Yes, it is a new order</button>
        </>}>
          <p>{dup}</p>
          <p className="muted">Duplicate orders are a common cause of wrong deliveries. Confirm only if you really need the same items again.</p>
        </Modal>
      )}

      {paste && (
        <Modal title="Paste an order message" onClose={() => setPaste(false)} footer={<>
          <button className="btn" onClick={() => setPaste(false)}>Cancel</button>
          <button className="btn primary" disabled={!pasteText.trim()} onClick={() => { applyRows(textToRows(pasteText), 'message'); setPaste(false); setPasteText('') }}>Read items</button>
        </>}>
          <p className="muted">Paste the list you would send on WhatsApp or e-mail, one item per line, e.g. "20 bags Cement, 50 kg bag" or "ROD-12 x 10".</p>
          <textarea rows={8} value={pasteText} onChange={(e) => setPasteText(e.target.value)} autoFocus />
        </Modal>
      )}
    </>
  )
}
