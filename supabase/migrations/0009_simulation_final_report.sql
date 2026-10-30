-- Totals for the Reports page from the final replicate runs (runs that are
-- not sensitivity replays of another run). Same conventions as
-- docs/chapter4_final/07_analysis/analyse_final.py: flagged = fail or warn,
-- positive = an order carrying a planted error. Runs as the caller, so the
-- admin/ops read policy on simulation_final_orders applies.
create or replace function public.simulation_final_report()
 returns jsonb
 language sql
 stable
 security invoker
 set search_path to 'public'
as $function$
  with o as (
    select * from simulation_final_orders where replay_of is null
  ), per_type as (
    select run_id, planted_error, bool_or(rule_targeted) rule_targeted, count(*) n,
           count(*) filter (where outcome = 'fail') blocked,
           count(*) filter (where outcome = 'warn') warned,
           count(*) filter (where flagged) flagged
    from o group by run_id, planted_error
  ), per_run as (
    select run_id, max(replicate) replicate, count(*) orders,
           count(*) filter (where planted_error <> 'clean' and flagged) tp,
           count(*) filter (where planted_error <> 'clean' and not flagged) fn,
           count(*) filter (where planted_error = 'clean' and flagged) fp,
           count(*) filter (where planted_error = 'clean' and not flagged) tn,
           count(*) filter (where planted_error <> 'clean' and rule_targeted and flagged) tgt_tp,
           count(*) filter (where planted_error <> 'clean' and rule_targeted) tgt_n,
           count(*) filter (where planted_error <> 'clean' and not rule_targeted and flagged) untgt_caught,
           count(*) filter (where planted_error <> 'clean' and not rule_targeted) untgt_n
    from o group by run_id
  )
  select coalesce(jsonb_agg(jsonb_build_object(
    'run_id', r.run_id, 'replicate', r.replicate, 'run_at', s.run_at, 'orders', r.orders,
    'tp', r.tp, 'fn', r.fn, 'fp', r.fp, 'tn', r.tn,
    'tgt_tp', r.tgt_tp, 'tgt_n', r.tgt_n, 'untgt_caught', r.untgt_caught, 'untgt_n', r.untgt_n,
    'by_type', (select jsonb_agg(jsonb_build_object('key', t.planted_error, 'rule_targeted', t.rule_targeted, 'n', t.n,
                  'blocked', t.blocked, 'warned', t.warned, 'flagged', t.flagged) order by t.planted_error)
                from per_type t where t.run_id = r.run_id)
  ) order by r.replicate), '[]')
  from per_run r left join simulation_runs s on s.id = r.run_id
$function$;

revoke execute on function public.simulation_final_report() from public, anon;
grant execute on function public.simulation_final_report() to authenticated;
