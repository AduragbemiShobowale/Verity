-- Verity condition results for the baseline session. Read-only. Run after the session, as an administrator.
-- Participants type the order reference and their participant ID in the order Notes field, for example "B-017 P03".
-- Elapsed time runs from the draft event (the order was first saved) to the approval decision recorded in the status
-- history: pending_approval -> awaiting_payment (approved) or pending_approval -> rejected. Orders blocked by validation
-- end at validation_failed; their elapsed time runs to that event and is reported separately.
-- Export each query's result as CSV: verity_orders.csv and verity_audit.csv.

-- 1. one row per baseline order
with b as (
  select o.*, c.name as customer, substring(o.notes from 'B-[0-9]{3}') as ref, substring(o.notes from 'P[0-9]{2}') as participant
  from orders o join customers c on c.id = o.customer_id
  where c.admin_note = 'baseline session dummy' and o.notes ~ 'B-[0-9]{3}'
), ev as (
  select e.order_id,
         min(e.at) filter (where e.to_status = 'draft') as draft_at,
         min(e.at) filter (where e.to_status = 'submitted') as first_submitted_at,
         max(e.at) filter (where e.to_status = 'submitted') as last_submitted_at,
         count(*) filter (where e.to_status = 'submitted') as submissions,
         min(e.at) filter (where e.to_status = 'pending_approval') as pending_at,
         min(e.at) filter (where e.from_status = 'pending_approval' and e.to_status = 'awaiting_payment') as approved_at,
         min(e.at) filter (where e.from_status = 'pending_approval' and e.to_status = 'rejected') as rejected_at,
         max(e.at) filter (where e.to_status = 'validation_failed') as last_failed_at,
         string_agg(coalesce(e.from_status::text, '-') || '>' || e.to_status, ' ' order by e.id) as path
  from order_events e where e.order_id in (select id from b) group by 1
)
select b.ref, b.participant, b.order_no, b.customer, b.status as final_status, b.validation_outcome,
       a.label as address_label, a.line as address_line, b.requested_date,
       (select string_agg(p.sku || ' x ' || oi.qty_ordered, '; ' order by p.sku) from order_items oi join products p on p.id = oi.product_id
         where oi.order_id = b.id and oi.qty_ordered > 0) as lines_entered,
       b.unmatched_lines::text as unmatched_lines,
       (select string_agg(distinct v.rule, '; ') from validation_results v where v.order_id = b.id and v.severity <> 'pass') as rules_ever_triggered,
       (select string_agg(v.message, ' | ') from validation_results v where v.order_id = b.id and v.current and v.severity <> 'pass') as current_messages,
       b.duplicate_confirmed, ev.submissions, ev.path,
       ev.draft_at, ev.first_submitted_at, ev.pending_at, ev.approved_at, ev.rejected_at, ev.last_failed_at,
       extract(epoch from coalesce(ev.approved_at, ev.rejected_at) - ev.draft_at) as seconds_draft_to_decision,
       extract(epoch from ev.last_failed_at - ev.draft_at) as seconds_draft_to_last_block,
       (select ap.comment from approvals ap where ap.order_id = b.id order by ap.id desc limit 1) as approver_comment
from b left join ev on ev.order_id = b.id left join addresses a on a.id = b.address_id
order by b.participant, b.ref;

-- 2. audit log entries for the same orders
select o.order_no, substring(o.notes from 'B-[0-9]{3}') as ref, substring(o.notes from 'P[0-9]{2}') as participant,
       l.at, l.action, l.old_value::text, l.new_value::text, p.email as by_user
from audit_log l
join orders o on o.id::text = l.entity_id and l.entity = 'order'
join customers c on c.id = o.customer_id and c.admin_note = 'baseline session dummy'
left join profiles p on p.id = l.user_id
where o.notes ~ 'B-[0-9]{3}'
order by o.order_no, l.at;
