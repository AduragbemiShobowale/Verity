-- Read-only. Orders entered by hand on 2026-10-30 with the demo accounts, with their full status history.
select o.order_no, c.name customer, o.status final_status, o.total, o.notes,
 (select json_agg(json_build_object('sku',p.sku,'qty',oi.qty_ordered) order by p.sku) from order_items oi join products p on p.id=oi.product_id where oi.order_id=o.id and oi.qty_ordered>0) lines,
 (select json_agg(json_build_object('from',e.from_status,'to',e.to_status,'at',e.at,'by',pr.email,'role',pr.role,'note',e.note) order by e.id) from order_events e left join profiles pr on pr.id=e.user_id where e.order_id=o.id) events,
 (select json_agg(json_build_object('rule',v.rule,'severity',v.severity,'message',v.message,'current',v.current) order by v.id) from validation_results v where v.order_id=o.id) validation_history,
 (select json_agg(json_build_object('amount',r.amount,'status',r.status,'credit_note',r.credit_note_no)) from refunds r where r.order_id=o.id) refunds,
 (select failed_attempts from delivery_codes dc where dc.order_id=o.id) wrong_code_attempts
from orders o join customers c on c.id=o.customer_id where o.created_at::date = date '2026-10-30';
