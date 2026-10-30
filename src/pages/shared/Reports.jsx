import { supabase, rpc } from '../../lib/supabase'
import { date, RULE_LABEL, STATUS } from '../../lib/format'
import { Card, PageHead, Kpi, Badge, Empty, Loading, useLoad, q } from '../../components/ui'

const CAT_LABEL = {
  clean: 'Clean order (no error)',
  bad_sku: 'SKU not in catalogue', inactive_product: 'Discontinued product', missing_address: 'Missing delivery address',
  missing_date: 'Missing delivery date', past_date: 'Delivery date in the past', qty_below_min: 'Quantity below minimum',
  qty_above_max: 'Quantity above maximum', fractional_qty: 'Fractional quantity', over_stock: 'Quantity above available stock',
  duplicate: 'Duplicate order', inactive_customer: 'Customer account not active', stale_price: 'Price changed after the order was saved',
  wrong_product: 'Wrong but valid product', qty_typo: 'Plausible quantity typing slip', wrong_address: 'Wrong saved address',
}
const ORDER = Object.keys(CAT_LABEL)
const pct = (k, n) => Math.round((1000 * k) / n) / 10
// One value per replicate, shown as a single figure when they agree and as a range when they differ
const span = (xs, unit = '%') => {
  const lo = Math.min(...xs), hi = Math.max(...xs)
  const f = (x) => (unit === '%' && x !== 100 ? x.toFixed(1) : String(x))
  return (lo === hi ? f(lo) : `${f(lo)}–${f(hi)}`) + unit
}

function Bars({ rows }) {
  const max = Math.max(...rows.map((r) => r[1]), 1)
  return (
    <div className="stack">
      {rows.map(([k, v]) => (
        <div key={k}>
          <div className="row between small"><span>{k}</span><strong>{v}</strong></div>
          <div className="bar"><span style={{ width: `${(v / max) * 100}%` }} /></div>
        </div>
      ))}
    </div>
  )
}

export default function Reports() {
  const { data } = useLoad(async () => {
    const [stats, reps] = await Promise.all([rpc('performance_stats'), q(supabase.rpc('simulation_final_report'))])
    return { stats, reps: reps || [] }
  })
  if (!data) return <Loading />
  const s = data.stats
  const reps = data.reps
  const acc = reps.map((r) => pct(r.tp + r.tn, r.orders))
  const types = reps.length ? ORDER.filter((k) => reps[0].by_type.some((t) => t.key === k)) : []
  const cell = (r, k) => r.by_type.find((t) => t.key === k)
  return (
    <>
      <PageHead hero title="Performance & success criteria" sub="Live figures from real orders, plus the final validation simulation reported in Chapter Four." />

      <Card title="Validation simulation" action={reps.length > 0 && <span className="muted small">{reps.length} runs of {reps[0].orders} orders · {date(reps[0].run_at)} · every run rolled back</span>}>
        {reps.length === 0 ? <Empty>No simulation results to show.</Empty> : (
          <div className="stack-lg">
            <div className="kpis">
              <Kpi label="Accuracy on all orders (target 90%)" value={span(acc)} alert={Math.max(...acc) < 90} />
              <Kpi label="Accuracy on error types the rules target" value={span(reps.map((r) => pct(r.tgt_tp + r.tn, r.tgt_n + r.fp + r.tn)))} />
              <Kpi label="Errors with no rule caught" value={span(reps.map((r) => r.untgt_caught), '')  + ' of ' + reps[0].untgt_n} alert />
              <Kpi label="Clean orders wrongly flagged" value={span(reps.map((r) => r.fp), '') + ' of ' + (reps[0].fp + reps[0].tn)} />
            </div>
            <div className="notice info">
              Accuracy = (erroneous orders flagged + clean orders passed) / orders. "Flagged" means blocked or sent to the Ops Desk with a warning.
              The rows marked "no rule" are realistic mistakes no rule checks for. They are included on purpose so the score is not just the rules grading themselves.
              Where the runs differ, the range across the {reps.length} runs is shown.
            </div>
            <div className="table-wrap"><table>
              <thead><tr><th>Planted error</th><th className="num">Orders per run</th>{reps.map((r) => <th key={r.run_id} className="num">Run {r.replicate}</th>)}<th className="num">Rate</th></tr></thead>
              <tbody>{types.map((k) => {
                const clean = k === 'clean'
                const rate = reps.map((r) => { const c = cell(r, k); return pct(clean ? c.n - c.flagged : c.flagged, c.n) })
                return (
                  <tr key={k}>
                    <td>{CAT_LABEL[k] || k} {!clean && !cell(reps[0], k).rule_targeted && <Badge tone="warn">no rule</Badge>}</td>
                    <td className="num">{cell(reps[0], k).n}</td>
                    {reps.map((r) => { const c = cell(r, k); return <td key={r.run_id} className="num">{clean ? c.n - c.flagged : c.flagged}</td> })}
                    <td className="num"><strong>{span(rate)}</strong><div className="muted small">{clean ? 'passed' : 'flagged'}</div></td>
                  </tr>
                )
              })}</tbody>
            </table></div>
          </div>
        )}
      </Card>

      <div className="kpis">
        <Kpi label="Orders submitted" value={s.orders_total} />
        <Kpi label="Passed validation first time" value={s.first_pass_rate == null ? '—' : s.first_pass_rate + '%'} />
        <Kpi label="Stored orders missing a mandatory field" value={s.mandatory_missing} alert={s.mandatory_missing > 0} />
        <Kpi label="Avg hours submit → delivered" value={s.avg_hours_submit_to_delivered ?? '—'} />
      </div>
      <div className="grid-2">
        <Card title="Errors caught per rule">
          {Object.keys(s.errors_by_rule).length === 0 ? <Empty>No validation errors yet.</Empty>
            : <Bars rows={Object.entries(s.errors_by_rule).map(([k, v]) => [RULE_LABEL[k] || k, v]).sort((a, b) => b[1] - a[1])} />}
        </Card>
        <Card title="Average hours spent in each stage">
          {Object.keys(s.avg_hours_by_stage).length === 0 ? <Empty>No completed stages yet.</Empty>
            : <Bars rows={Object.entries(s.avg_hours_by_stage).map(([k, v]) => [STATUS[k]?.label || k, Number(v)])} />}
          <p className="muted small" style={{ marginTop: 10 }}>The 30–50% speed claim needs a manual baseline: time staff re-keying ~30 sample orders from Excel/WhatsApp, then compare with these stage times.</p>
        </Card>
        <Card title="Approvals">
          <Bars rows={[['Auto-approved by rule', s.auto_approved], ['Approved by the Ops Desk', s.manually_approved]]} />
        </Card>
        <Card title="Order source">
          {Object.keys(s.by_source).length === 0 ? <Empty>No orders yet.</Empty> : <Bars rows={Object.entries(s.by_source)} />}
        </Card>
      </div>
    </>
  )
}
