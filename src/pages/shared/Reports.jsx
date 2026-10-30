import { supabase, rpc } from '../../lib/supabase'
import { useAuth } from '../../context/AuthContext'
import { dateTime, RULE_LABEL, STATUS } from '../../lib/format'
import { Card, PageHead, Kpi, Badge, Empty, Loading, useLoad, q, useAction } from '../../components/ui'

const CAT_LABEL = {
  clean: 'Clean order (no error)',
  bad_sku: 'SKU not in catalogue', missing_address: 'Missing address', missing_date: 'Missing date', past_date: 'Date in the past',
  qty_below_min: 'Quantity below minimum', qty_above_max: 'Quantity above maximum', fractional_qty: 'Fractional quantity',
  over_stock: 'More than available stock', duplicate: 'Duplicate order', inactive_product: 'Discontinued product',
  wrong_product: 'Wrong but valid product picked', qty_typo: 'Plausible quantity typo (20→200)', wrong_address: 'Wrong saved address chosen',
}
const UNTARGETED = ['wrong_product', 'qty_typo', 'wrong_address']

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
  const { role } = useAuth()
  const [run, busy] = useAction()
  const { data, reload } = useLoad(async () => {
    const [stats, sims] = await Promise.all([rpc('performance_stats'), q(supabase.from('simulation_runs').select('*').not('summary->by_category', 'is', null).order('id', { ascending: false }).limit(5))])
    return { stats, sims }
  })
  if (!data) return <Loading />
  const s = data.stats
  // Only runs whose summary holds per-category counts. The final replicate runs keep their results in simulation_final_orders instead.
  const sim = data.sims.find((x) => x.summary?.by_category && !x.summary.superseded)
  const cats = sim ? Object.entries(sim.summary.by_category).sort((a, b) => (UNTARGETED.includes(a[0]) - UNTARGETED.includes(b[0])) || b[1].n - a[1].n) : []
  return (
    <>
      <PageHead hero title="Performance & success criteria" sub="Live figures from real orders, plus the latest validation simulation.">
        {role === 'admin' && <button className="btn primary" disabled={busy} onClick={() => run(async () => { await rpc('run_simulation', { p_n: 500, p_seed: Math.random() }); reload() }, 'Simulation finished.')}>{busy ? 'Running 500 orders…' : 'Run 500-order simulation'}</button>}
      </PageHead>

      <Card title="Validation simulation" action={sim && <span className="muted small">{dateTime(sim.run_at)} · {sim.orders} orders · nothing saved except this summary</span>}>
        {!sim ? <Empty>No simulation yet.{role === 'admin' ? ' Run one above.' : ''}</Empty> : (
          <div className="stack-lg">
            <div className="kpis">
              <Kpi label="Accuracy on all orders (target 90%)" value={sim.summary.accuracy_all + '%'} alert={sim.summary.accuracy_all < 90} />
              <Kpi label="Accuracy on error types the rules target" value={sim.summary.accuracy_targeted + '%'} />
              <Kpi label="Untargeted errors caught" value={`${sim.summary.untargeted_caught}/${sim.summary.untargeted}`} alert />
              <Kpi label="Clean orders wrongly flagged" value={`${sim.summary.clean - sim.summary.clean_passed}/${sim.summary.clean}`} />
            </div>
            <div className="notice info">
              Accuracy = (erroneous orders flagged + clean orders passed) / orders. "Flagged" means blocked or sent to the Ops Desk with a warning.
              The untargeted rows are realistic mistakes no rule checks for; they are included on purpose so the score is not just the rules grading themselves.
            </div>
            <div className="table-wrap"><table>
              <thead><tr><th>Planted error</th><th className="num">Orders</th><th className="num">Blocked</th><th className="num">Flagged (incl. warnings)</th><th className="num">Rate</th></tr></thead>
              <tbody>{cats.map(([k, v]) => {
                const rate = k === 'clean' ? (v.n - v.flagged) / v.n : v.flagged / v.n
                return (
                  <tr key={k}>
                    <td>{CAT_LABEL[k] || k} {UNTARGETED.includes(k) && <Badge tone="warn">no rule</Badge>}</td>
                    <td className="num">{v.n}</td><td className="num">{v.blocked}</td><td className="num">{v.flagged}</td>
                    <td className="num"><strong>{Math.round(rate * 100)}%</strong>{k === 'clean' && <div className="muted small">passed</div>}</td>
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
