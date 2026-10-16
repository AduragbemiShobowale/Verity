import { useState } from 'react'
import toast from 'react-hot-toast'
import { rpc, uploadFile } from '../../lib/supabase'
import { useAuth } from '../../context/AuthContext'
import { AuthFrame } from './AuthPages'
import { date } from '../../lib/format'

// Step 2 of registration (also used to resubmit after "more info" or a rejection).
export function RegistrationForm({ existing, note }) {
  const { user, refresh, signOut } = useAuth()
  const [f, setF] = useState({
    name: existing?.name || '', reg_no: existing?.reg_no || '', contact_name: existing?.contact_name || user?.user_metadata?.full_name || '',
    phone: existing?.phone || '', address: existing?.address || '', industry: existing?.industry || '',
    expected_volume: existing?.expected_volume ?? '',
  })
  const [files, setFiles] = useState([])
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })

  const submit = async (e) => {
    e.preventDefault()
    setErr(null)
    if (!files.length) return setErr('Attach your business registration certificate (PDF, JPG or PNG, up to 5 MB).')
    for (const file of files) {
      if (file.size > 5 * 1024 * 1024) return setErr(`${file.name} is larger than 5 MB.`)
    }
    setBusy(true)
    try {
      const documents = []
      for (const file of files) documents.push(await uploadFile('registration-docs', file, user.id))
      const r = await rpc('submit_registration', { p: { ...f, documents } })
      if (r.outcome === 'auto_approved') toast.success('Your account is active.')
      await refresh()
    } catch (e2) {
      setErr(e2.message)
      setBusy(false)
    }
  }

  return (
    <AuthFrame wide>
      <div>
        <h1>{existing ? 'Update your application' : 'Company details'}</h1>
        <p className="muted">Step 2 of 2. We review every new business before it can order.</p>
      </div>
      {note && <div className="notice warn"><strong>Note from our team</strong>{note}</div>}
      <form className="form-grid" onSubmit={submit}>
        <label className="field full">Company name<input value={f.name} onChange={set('name')} required /></label>
        <label className="field">Registration number (RC)<input value={f.reg_no} onChange={set('reg_no')} placeholder="RC-1234567" required /></label>
        <label className="field">Industry<input value={f.industry} onChange={set('industry')} placeholder="Construction" /></label>
        <label className="field">Contact person<input value={f.contact_name} onChange={set('contact_name')} required /></label>
        <label className="field">Phone<input value={f.phone} onChange={set('phone')} inputMode="tel" required /></label>
        <label className="field full">Business address<input value={f.address} onChange={set('address')} required /></label>
        <label className="field">Expected orders per month<input type="number" min="0" value={f.expected_volume} onChange={set('expected_volume')} /></label>
        <label className="field">Documents <span className="hint">Business registration certificate</span>
          <input type="file" multiple accept=".pdf,.jpg,.jpeg,.png" onChange={(e) => setFiles([...e.target.files])} style={{ paddingTop: 6 }} />
        </label>
        {err && <div className="notice bad full">{err}</div>}
        <div className="row full">
          <button className="btn primary lg" disabled={busy}>{busy ? 'Submitting…' : 'Submit for review'}</button>
          <button type="button" className="btn ghost" onClick={signOut}>Sign out</button>
        </div>
      </form>
    </AuthFrame>
  )
}

export function AccountStatus() {
  const { customer, signOut, refresh } = useAuth()
  const s = customer.status
  if (s === 'more_info') return <RegistrationForm existing={customer} note={customer.admin_note} />
  if (s === 'rejected' && (!customer.reapply_after || new Date(customer.reapply_after) <= new Date())) {
    return <RegistrationForm existing={customer} note={`Your previous application was not accepted: ${customer.rejection_reason || ''} You can apply again now.`} />
  }
  const copy = {
    awaiting_review: ['Application received', 'We are reviewing your application. You will get an e-mail when we decide, and this page will open your dashboard.'],
    rejected: ['Application not accepted', `${customer.rejection_reason || ''} You can apply again from ${date(customer.reapply_after)}.`],
    on_hold: ['Account on hold', customer.admin_note || 'Your account is on hold. Contact us for details.'],
    blocked: ['Account blocked', customer.admin_note || 'This account cannot place orders. Contact us for details.'],
  }[s] || ['Account status', s]
  return (
    <AuthFrame>
      <h1>{copy[0]}</h1>
      <p>{copy[1]}</p>
      <div className="card card-pad stack">
        <div className="row between"><span className="muted">Company</span><strong>{customer.name}</strong></div>
        <div className="row between"><span className="muted">Registration no.</span><span>{customer.reg_no}</span></div>
        <div className="row between"><span className="muted">Status</span><span className="badge t-warn">{s.replace('_', ' ')}</span></div>
      </div>
      <p className="muted small">Questions? Call +234 800 000 0000 or reply to our e-mail.</p>
      <div className="row"><button className="btn" onClick={refresh}>Check again</button><button className="btn ghost" onClick={signOut}>Sign out</button></div>
    </AuthFrame>
  )
}
