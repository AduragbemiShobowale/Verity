-- Verity: workflow functions (generated from the live database)
-- Every state change goes through one of these. Each checks the caller's
-- role, moves the order through the state machine (_transition) and writes
-- the audit trail; the client never updates workflow tables directly.
-- Note: no function uses DELETE. Removed order lines keep qty_ordered = 0,
-- superseded validation results get current = false, and delivery codes are
-- upserted, so history is never lost.

CREATE OR REPLACE FUNCTION public._amount_paid(p_order uuid)
 RETURNS numeric
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
  select coalesce((select i.total from invoices i where i.order_id = p_order and i.status in ('paid','credited')), 0)
$function$
;

CREATE OR REPLACE FUNCTION public._amount_refunded(p_order uuid)
 RETURNS numeric
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
  select coalesce(sum(amount), 0) from refunds where order_id = p_order
$function$
;

CREATE OR REPLACE FUNCTION public._approve(p_order uuid, p_comment text)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare o orders; i record;
begin
  select * into o from orders where id = p_order for update;
  for i in select oi.*, p.name, p.on_hand, p.reserved from order_items oi
           join products p on p.id = oi.product_id where oi.order_id = p_order and oi.qty_ordered > 0
           order by oi.product_id for update of p loop
    if i.on_hand - i.reserved < i.qty_ordered then
      perform _err(format('Not enough stock left for %s. It was taken by another order after this one was submitted.', i.name));
    end if;
    update products set reserved = reserved + i.qty_ordered where id = i.product_id;
    update order_items set qty_reserved = i.qty_ordered where id = i.id;
    insert into stock_movements (product_id, type, qty, reason, order_id, user_id)
    values (i.product_id, 'reserve', i.qty_ordered, 'Order approved', p_order, auth.uid());
  end loop;

  insert into invoices (order_id, customer_id, subtotal, delivery_fee, tax, total, due_at)
  values (p_order, o.customer_id, o.subtotal, o.delivery_fee, o.tax, o.total,
          now() + make_interval(hours => setting_num('payment_window_hours')::int))
  on conflict (order_id) do update set subtotal = excluded.subtotal, delivery_fee = excluded.delivery_fee,
    tax = excluded.tax, total = excluded.total, due_at = excluded.due_at, status = 'issued';

  insert into approvals (order_id, approver_id, decision, comment) values (p_order, auth.uid(), 'approved', p_comment);
  update orders set payment_attempts_allowed = setting_num('max_payment_attempts')::int where id = p_order;
  perform _transition(p_order, 'awaiting_payment', p_comment);
  perform _notify_customer(o.customer_id, 'approved', 'Order approved: ' || o.order_no,
    format('Your invoice of %s is ready. Pay within %s hours and upload the proof.', o.total, setting_num('payment_window_hours')),
    p_order, '/invoices', true);
  for i in select product_id from order_items where order_id = p_order and qty_ordered > 0 loop
    perform _check_low_stock(i.product_id);
  end loop;
end $function$
;

CREATE OR REPLACE FUNCTION public._cancel(p_order uuid, p_reason text)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare o orders;
begin
  select * into o from orders where id = p_order for update;
  perform _release_reservation(p_order, 'Order cancelled');
  perform _restock_picked(p_order, 'Returned to stock from cancelled order');
  update deliveries set current = false, outcome = coalesce(outcome, 'reassigned') where order_id = p_order and current;
  update delivery_codes set locked = true where order_id = p_order;
  update invoices set status = 'cancelled' where order_id = p_order and status = 'issued';
  update orders set cancel_reason = p_reason, cancel_requested_reason = null where id = p_order;
  perform _transition(p_order, 'cancelled', p_reason);
  if _amount_paid(p_order) > _amount_refunded(p_order) then
    perform _raise_refund(p_order, _amount_paid(p_order) - _amount_refunded(p_order), 'Order cancelled: ' || p_reason);
  end if;
  perform _notify_customer(o.customer_id, 'cancelled', 'Order cancelled: ' || o.order_no, p_reason, p_order, '/orders/' || p_order, true);
end $function$
;

CREATE OR REPLACE FUNCTION public._check_low_stock(p_product uuid)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare p products;
begin
  select * into p from products where id = p_product;
  if p.active and p.on_hand - p.reserved <= p.reorder_level and not exists (
      select 1 from notifications n
      where n.event = 'low_stock' and n.link = '/stock/' || p.id and n.created_at > now() - interval '24 hours') then
    perform _notify_role(r, 'low_stock', 'Low stock: ' || p.name,
      format('%s (%s) has %s available, reorder level %s.', p.name, p.sku, greatest(p.on_hand - p.reserved, 0), p.reorder_level),
      null, '/stock/' || p.id, false)
    from unnest(array['admin','ops','warehouse']::app_role[]) r;
  end if;
end $function$
;

CREATE OR REPLACE FUNCTION public._err(msg text)
 RETURNS void
 LANGUAGE plpgsql
AS $function$
begin raise exception using message = msg, errcode = 'P0001'; end $function$
;

CREATE OR REPLACE FUNCTION public._issue_code(p_order uuid)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare v_code text; v_cust uuid; v_b bytea := extensions.gen_random_bytes(4); v_n bigint;
begin
  v_n := (get_byte(v_b, 0)::bigint * 16777216) + (get_byte(v_b, 1) * 65536) + (get_byte(v_b, 2) * 256) + get_byte(v_b, 3);
  v_code := lpad((v_n % 1000000)::text, 6, '0');
  select customer_id into v_cust from orders where id = p_order;
  insert into delivery_codes (order_id, code_hash, expires_at)
  values (p_order, extensions.crypt(v_code, extensions.gen_salt('bf', 8)),
          now() + make_interval(days => setting_num('delivery_code_valid_days')::int))
  on conflict (order_id) do update set code_hash = excluded.code_hash, expires_at = excluded.expires_at,
    issued_at = now(), failed_attempts = 0, locked = false, used_at = null;
  insert into delivery_code_reveals (order_id, customer_id, code) values (p_order, v_cust, v_code)
  on conflict (order_id) do update set code = excluded.code;
end $function$
;

CREATE OR REPLACE FUNCTION public._notify_customer(p_customer uuid, p_event text, p_title text, p_body text, p_order uuid DEFAULT NULL::uuid, p_link text DEFAULT NULL::text, p_email boolean DEFAULT false)
 RETURNS void
 LANGUAGE sql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
  insert into notifications (user_id, event, title, body, order_id, link, send_email)
  select cu.user_id, p_event, p_title, p_body, p_order, p_link, p_email
  from customer_users cu join profiles p on p.id = cu.user_id
  where cu.customer_id = p_customer and p.status = 'active'
$function$
;

CREATE OR REPLACE FUNCTION public._notify_role(p_role app_role, p_event text, p_title text, p_body text, p_order uuid DEFAULT NULL::uuid, p_link text DEFAULT NULL::text, p_email boolean DEFAULT false)
 RETURNS void
 LANGUAGE sql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
  insert into notifications (user_id, event, title, body, order_id, link, send_email)
  select id, p_event, p_title, p_body, p_order, p_link, p_email
  from profiles where role = p_role and status = 'active'
$function$
;

CREATE OR REPLACE FUNCTION public._notify_user(p_user uuid, p_event text, p_title text, p_body text, p_order uuid DEFAULT NULL::uuid, p_link text DEFAULT NULL::text, p_email boolean DEFAULT false)
 RETURNS void
 LANGUAGE sql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
  insert into notifications (user_id, event, title, body, order_id, link, send_email)
  values (p_user, p_event, p_title, p_body, p_order, p_link, p_email)
$function$
;

CREATE OR REPLACE FUNCTION public._order_no(p_order uuid)
 RETURNS text
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
  select order_no from orders where id = p_order
$function$
;

CREATE OR REPLACE FUNCTION public._pack(p_order uuid, p_note text DEFAULT NULL::text)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare v_cust uuid;
begin
  select customer_id into v_cust from orders where id = p_order;
  perform _transition(p_order, 'packed', p_note);
  perform _issue_code(p_order);
  perform _notify_role('dispatch', 'ready_for_dispatch', 'Ready for dispatch: ' || _order_no(p_order),
                       'Packed and waiting for a driver.', p_order, '/dispatch');
  perform _notify_customer(v_cust, 'packed', 'Order packed: ' || _order_no(p_order),
                           'Your order is packed and waiting for a driver.', p_order, '/orders/' || p_order);
end $function$
;

CREATE OR REPLACE FUNCTION public._raise_refund(p_order uuid, p_amount numeric, p_reason text)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare v_amt numeric; v_cust uuid;
begin
  v_amt := least(round(p_amount, 2), _amount_paid(p_order) - _amount_refunded(p_order));
  if v_amt <= 0 then return; end if;
  select customer_id into v_cust from orders where id = p_order;
  insert into refunds (order_id, customer_id, amount, reason, requested_by)
  values (p_order, v_cust, v_amt, p_reason, auth.uid());
  perform audit('refund', p_order::text, 'requested', null, jsonb_build_object('amount', v_amt, 'reason', p_reason));
  perform _notify_role('finance', 'refund_requested', 'Refund to process: ' || _order_no(p_order),
                       format('%s to refund. Reason: %s', v_amt, p_reason), p_order, '/finance/refunds');
end $function$
;

CREATE OR REPLACE FUNCTION public._recalc_order(p_order uuid)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare v_sub numeric; v_fee numeric; v_tax numeric;
begin
  select coalesce(sum(qty_ordered * unit_price), 0) into v_sub from order_items where order_id = p_order;
  select coalesce(r.delivery_fee, 0) into v_fee
    from orders o left join addresses a on a.id = o.address_id left join regions r on r.id = a.region_id
    where o.id = p_order;
  v_fee := coalesce(v_fee, 0);
  v_tax := round((v_sub + v_fee) * setting_num('tax_rate') / 100, 2);
  update orders set subtotal = v_sub, delivery_fee = v_fee, tax = v_tax, total = v_sub + v_fee + v_tax,
                    updated_at = now()
  where id = p_order;
end $function$
;

CREATE OR REPLACE FUNCTION public._release_reservation(p_order uuid, p_reason text)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare i record;
begin
  for i in select * from order_items where order_id = p_order and qty_reserved > 0 order by product_id loop
    update products set reserved = greatest(reserved - i.qty_reserved, 0) where id = i.product_id;
    insert into stock_movements (product_id, type, qty, reason, order_id, user_id)
    values (i.product_id, 'release', i.qty_reserved, p_reason, p_order, auth.uid());
    update order_items set qty_reserved = 0 where id = i.id;
  end loop;
end $function$
;

CREATE OR REPLACE FUNCTION public._require(VARIADIC roles app_role[])
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
begin
  if not has_role(variadic roles) then
    perform _err('You do not have permission to do this.');
  end if;
end $function$
;

CREATE OR REPLACE FUNCTION public._restock_picked(p_order uuid, p_reason text)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare i record;
begin
  for i in select * from order_items where order_id = p_order and qty_picked > 0 order by product_id loop
    update products set on_hand = on_hand + i.qty_picked where id = i.product_id;
    insert into stock_movements (product_id, type, qty, reason, order_id, user_id)
    values (i.product_id, 'adjust', i.qty_picked, p_reason, p_order, auth.uid());
    update order_items set qty_picked = 0 where id = i.id;
  end loop;
end $function$
;

CREATE OR REPLACE FUNCTION public._snapshot_item()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
begin
  select sku, name, unit into new.product_sku, new.product_name, new.unit from products where id = new.product_id;
  return new;
end $function$
;

CREATE OR REPLACE FUNCTION public._transition(p_order uuid, p_to order_status, p_note text DEFAULT NULL::text)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare v_from order_status;
begin
  select status into v_from from orders where id = p_order for update;
  if v_from is null then perform _err('Order not found.'); end if;
  if not exists (select 1 from order_transitions where from_status = v_from and to_status = p_to) then
    perform _err(format('Order cannot move from %s to %s.', v_from, p_to));
  end if;
  update orders set status = p_to, updated_at = now() where id = p_order;
  insert into order_events (order_id, from_status, to_status, note, user_id)
  values (p_order, v_from, p_to, p_note, auth.uid());
  perform audit('order', p_order::text, 'status_change',
                jsonb_build_object('status', v_from),
                jsonb_build_object('status', p_to, 'note', p_note));
end $function$
;

CREATE OR REPLACE FUNCTION public._validate(p_order uuid)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  o orders; c customers; a addresses;
  i record; u jsonb;
  v_tol numeric := setting_num('price_tolerance');
  v_factor numeric := setting_num('unusual_qty_factor');
  v_avg numeric; v_n int; v_avail int;
  v_dup text;
  v_outcome severity;
  v_items int;
begin
  select * into o from orders where id = p_order;
  select * into c from customers where id = o.customer_id;
  update validation_results set current = false where order_id = p_order and current;

  -- 1 mandatory fields
  select count(*) into v_items from order_items where order_id = p_order and qty_ordered > 0;
  if v_items = 0 and jsonb_array_length(o.unmatched_lines) = 0 then
    perform _vr(p_order, 'mandatory', 'fail', 'items', 'Add at least one product.');
  end if;
  if o.address_id is null then perform _vr(p_order, 'mandatory', 'fail', 'address_id', 'Choose a delivery address.'); end if;
  if o.requested_date is null then perform _vr(p_order, 'mandatory', 'fail', 'requested_date', 'Choose a delivery date.'); end if;

  -- 2 SKU (including upload lines that did not match the catalogue)
  for u in select * from jsonb_array_elements(o.unmatched_lines) loop
    perform _vr(p_order,
      case when u->>'problem' ilike '%quantity%' then 'quantity' else 'sku' end, 'fail', 'unmatched',
      coalesce('Row ' || (u->>'row') || ': ', '') || coalesce(nullif(u->>'sku',''), u->>'name', 'line') || ' - ' || coalesce(u->>'problem', 'not in the catalogue'));
  end loop;
  for i in select oi.*, p.sku, p.name, p.active, p.price, p.min_qty, p.max_qty, p.on_hand, p.reserved
           from order_items oi join products p on p.id = oi.product_id
           where oi.order_id = p_order and oi.qty_ordered > 0 loop
    if not i.active then perform _vr(p_order, 'sku', 'fail', i.product_id::text, i.sku || ' is no longer sold. Remove it.'); end if;
    -- 3 quantity
    if i.qty_ordered < i.min_qty or i.qty_ordered > i.max_qty then
      perform _vr(p_order, 'quantity', 'fail', i.product_id::text, format('%s: quantity must be between %s and %s.', i.name, i.min_qty, i.max_qty));
    end if;
    -- 4 stock (exact count only shown when low)
    v_avail := greatest(i.on_hand - i.reserved, 0);
    if i.qty_ordered > v_avail then
      perform _vr(p_order, 'stock', 'fail', i.product_id::text,
        case when v_avail = 0 then i.name || ' is out of stock.'
             when v_avail <= setting_num('low_stock_warn_qty') then format('%s: only %s left. Reduce the quantity.', i.name, v_avail)
             else i.name || ': not enough stock for this quantity. Reduce it.' end);
    end if;
    -- 6 pricing
    if abs(i.unit_price - i.price) > v_tol then
      perform _vr(p_order, 'pricing', 'fail', i.product_id::text,
        format('%s: price changed from %s to %s. Save the order again to update it.', i.name, i.unit_price, i.price));
    end if;
    -- 9 unusual quantity
    select avg(oi2.qty_ordered), count(*) into v_avg, v_n
      from order_items oi2 join orders o2 on o2.id = oi2.order_id
      where o2.customer_id = o.customer_id and oi2.product_id = i.product_id and o2.id <> p_order and oi2.qty_ordered > 0
        and o2.submitted_at is not null and o2.status not in ('cancelled','rejected','validation_failed');
    if v_n >= 3 and i.qty_ordered > v_avg * v_factor then
      perform _vr(p_order, 'unusual_quantity', 'warn', i.product_id::text,
        format('%s: %s is far above this customer''s usual %s.', i.name, i.qty_ordered, round(v_avg)));
    end if;
  end loop;

  -- 5 customer status
  if c.status <> 'active' then perform _vr(p_order, 'customer_status', 'fail', 'customer', 'The customer account is not active.'); end if;

  -- 8 delivery date and address
  if o.requested_date is not null and o.requested_date < current_date then
    perform _vr(p_order, 'delivery', 'fail', 'requested_date', 'The delivery date is in the past.');
  end if;
  if o.address_id is not null then
    select * into a from addresses where id = o.address_id;
    if a.customer_id is distinct from o.customer_id or not a.active then
      perform _vr(p_order, 'delivery', 'fail', 'address_id', 'Choose one of your saved addresses.');
    elsif cardinality(c.allowed_region_ids) > 0 and not (a.region_id = any(c.allowed_region_ids)) then
      perform _vr(p_order, 'delivery', 'fail', 'address_id', 'We do not deliver to this region for your account.');
    end if;
  end if;

  -- 7 duplicate
  select o2.order_no into v_dup from orders o2
  where o2.customer_id = o.customer_id and o2.id <> p_order
    and o2.submitted_at > now() - make_interval(hours => setting_num('duplicate_window_hours')::int)
    and o2.status not in ('cancelled','rejected','validation_failed','draft')
    and (select coalesce(jsonb_agg(jsonb_build_array(product_id, qty_ordered) order by product_id), '[]') from order_items where order_id = o2.id and qty_ordered > 0)
      = (select coalesce(jsonb_agg(jsonb_build_array(product_id, qty_ordered) order by product_id), '[]') from order_items where order_id = p_order and qty_ordered > 0)
  order by o2.submitted_at desc limit 1;
  if v_dup is not null and v_items > 0 then
    perform _vr(p_order, 'duplicate', 'warn', 'items',
      case when o.duplicate_confirmed then format('Same items as %s. Customer confirmed this is a new order.', v_dup)
           else format('This looks like a repeat of %s. Confirm it is a new order.', v_dup) end);
  end if;

  select case when bool_or(severity = 'fail') then 'fail'::severity
              when bool_or(severity = 'warn') then 'warn'::severity
              else 'pass'::severity end
    into v_outcome from validation_results where order_id = p_order and current;
  v_outcome := coalesce(v_outcome, 'pass');
  if not exists (select 1 from validation_results where order_id = p_order and current) then
    perform _vr(p_order, 'all', 'pass', null, 'Every rule passed.');
  end if;
  update orders set validation_outcome = v_outcome where id = p_order;

  return jsonb_build_object(
    'outcome', v_outcome,
    'duplicate_unconfirmed', v_dup is not null and v_items > 0 and not o.duplicate_confirmed,
    'results', (select jsonb_agg(jsonb_build_object('rule', rule, 'severity', severity, 'field', field, 'message', message) order by severity desc, id)
                from validation_results where order_id = p_order and current));
end $function$
;

CREATE OR REPLACE FUNCTION public._vr(p_order uuid, p_rule text, p_sev severity, p_field text, p_msg text)
 RETURNS void
 LANGUAGE sql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
  insert into validation_results (order_id, rule, severity, field, message) values (p_order, p_rule, p_sev, p_field, p_msg)
$function$
;

CREATE OR REPLACE FUNCTION public.adjust_stock(p_product uuid, p_delta integer, p_reason text)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare v_on int;
begin
  perform _require('warehouse');
  if trim(coalesce(p_reason,'')) = '' then perform _err('A reason is required for every adjustment.'); end if;
  if p_delta is null or p_delta = 0 then perform _err('Enter a non-zero change.'); end if;
  select on_hand into v_on from products where id = p_product for update;
  if v_on + p_delta < 0 then perform _err(format('On hand would go below zero (now %s).', v_on)); end if;
  update products set on_hand = on_hand + p_delta where id = p_product;
  insert into stock_movements (product_id, type, qty, reason, user_id) values (p_product, 'adjust', p_delta, trim(p_reason), auth.uid());
  perform audit('product', p_product::text, 'stock_adjust', jsonb_build_object('on_hand', v_on), jsonb_build_object('on_hand', v_on + p_delta, 'reason', p_reason));
  perform _check_low_stock(p_product);
end $function$
;

CREATE OR REPLACE FUNCTION public.allow_payment_attempt(p_order uuid, p_note text)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare o orders;
begin
  perform _require('ops');
  select * into o from orders where id = p_order for update;
  if o.status <> 'payment_rejected' then perform _err('Only orders with a rejected payment can get another attempt.'); end if;
  update orders set payment_attempts_allowed = payment_attempts_allowed + 1 where id = p_order;
  update invoices set due_at = greatest(due_at, now() + make_interval(hours => setting_num('payment_reupload_grace_hours')::int))
  where order_id = p_order;
  perform audit('order', p_order::text, 'extra_payment_attempt', null, jsonb_build_object('note', p_note));
  perform _notify_customer(o.customer_id, 'payment_retry', 'You can upload a new payment proof',
    coalesce(nullif(p_note,''), 'The Ops Desk has allowed another upload.'), p_order, '/invoices', true);
end $function$
;

CREATE OR REPLACE FUNCTION public.approve_order(p_order uuid, p_comment text DEFAULT NULL::text)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare v_status order_status;
begin
  perform _require('ops');
  select status into v_status from orders where id = p_order for update;
  if v_status <> 'pending_approval' then perform _err('Only orders waiting for approval can be approved.'); end if;
  perform _approve(p_order, coalesce(nullif(trim(p_comment),''), 'Approved by Ops Desk'));
end $function$
;

CREATE OR REPLACE FUNCTION public.assign_delivery(p_orders uuid[], p_driver uuid, p_vehicle integer)
 RETURNS integer
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare v uuid; v_status order_status; n int := 0; v_list text := '';
begin
  perform _require('dispatch');
  if not exists (select 1 from profiles p join drivers d on d.user_id = p.id
                 where p.id = p_driver and p.role = 'driver' and p.status = 'active' and d.active) then
    perform _err('Choose an active driver.');
  end if;
  if p_vehicle is not null and not exists (select 1 from vehicles where id = p_vehicle and active) then
    perform _err('Choose an active vehicle.');
  end if;
  foreach v in array p_orders loop
    select status into v_status from orders where id = v for update;
    if v_status is null or v_status not in ('packed','delivery_failed') then
      perform _err(format('%s is not ready for dispatch.', coalesce(_order_no(v), 'An order')));
    end if;
    update deliveries set current = false, outcome = coalesce(outcome, 'reassigned') where order_id = v and current;
    insert into deliveries (order_id, driver_id, vehicle_id, assigned_by) values (v, p_driver, p_vehicle, auth.uid());
    if not exists (select 1 from delivery_codes where order_id = v and expires_at > now() and not locked and used_at is null) then
      perform _issue_code(v);
    end if;
    perform _transition(v, 'assigned', 'Assigned to driver');
    v_list := v_list || _order_no(v) || ' ';
    n := n + 1;
  end loop;
  perform _notify_user(p_driver, 'assigned', format('%s new deliver%s', n, case when n = 1 then 'y' else 'ies' end),
                       trim(v_list), null, '/driver');
  return n;
end $function$
;

CREATE OR REPLACE FUNCTION public.cancel_order(p_order uuid, p_reason text)
 RETURNS text
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare o orders;
begin
  select * into o from orders where id = p_order and customer_id = my_customer_id() for update;
  if o.id is null then perform _err('Order not found.'); end if;
  if trim(coalesce(p_reason,'')) = '' then p_reason := 'Cancelled by customer'; end if;
  if o.status in ('draft','validation_failed','rejected','pending_approval','awaiting_payment','payment_rejected') then
    perform _cancel(p_order, p_reason);
    return 'cancelled';
  elsif o.status in ('payment_verification','paid','picking','shortage_hold','packed','assigned') then
    update orders set cancel_requested_reason = p_reason where id = p_order;
    perform audit('order', p_order::text, 'cancel_requested', null, jsonb_build_object('reason', p_reason));
    perform _notify_role('ops', 'cancel_requested', 'Cancellation request: ' || o.order_no, p_reason, p_order, '/ops/orders/' || p_order);
    return 'requested';
  else
    perform _err('This order is already with the driver or finished, so it cannot be cancelled. Contact us about a return.');
  end if;
end $function$
;

CREATE OR REPLACE FUNCTION public.check_order(p_order uuid)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare v_status order_status;
begin
  select status into v_status from orders where id = p_order;
  if is_my_order(p_order) and v_status in ('draft','validation_failed','rejected') then return _validate(p_order); end if;
  if has_role('ops','admin') and v_status in ('draft','validation_failed','rejected','pending_approval') then return _validate(p_order); end if;
  perform _err('This order cannot be re-checked now.');
end $function$
;

CREATE OR REPLACE FUNCTION public.choose_shortage(p_order uuid, p_choice shortage_choice)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare o orders; v_short numeric; v_any_picked boolean; v_by_ops boolean := has_role('ops');
begin
  select * into o from orders where id = p_order for update;
  if o.id is null or not (o.customer_id = my_customer_id() or v_by_ops) then perform _err('Order not found.'); end if;
  if o.status <> 'shortage_hold' then perform _err('This order is not on shortage hold.'); end if;

  perform audit('order', p_order::text, 'shortage_choice', null,
                jsonb_build_object('choice', p_choice, 'by', case when v_by_ops then 'ops' else 'customer' end));

  if p_choice = 'wait_restock' then
    update orders set shortage_choice = 'wait_restock' where id = p_order;
    perform _notify_role('ops', 'shortage_choice', 'Customer will wait: ' || o.order_no, 'Waiting for restock.', p_order, '/ops/shortages');
    perform _notify_role('warehouse', 'shortage_choice', 'Waiting for restock: ' || o.order_no, 'Resume picking when stock arrives.', p_order, '/warehouse/pick');
    return;
  end if;

  select coalesce(bool_or(qty_picked > 0), false) into v_any_picked from order_items where order_id = p_order;
  if p_choice = 'cancel_order' or not v_any_picked then
    update orders set shortage_choice = 'cancel_order' where id = p_order;
    perform _cancel(p_order, 'Cancelled after stock shortage');
    return;
  end if;

  -- deliver what was found, refund the rest (items plus their tax)
  update orders set shortage_choice = 'deliver_available' where id = p_order;
  perform _release_reservation(p_order, 'Shortage: customer accepted partial delivery');
  select sum((qty_ordered - qty_picked) * unit_price) into v_short from order_items where order_id = p_order;
  perform _raise_refund(p_order, v_short * (1 + setting_num('tax_rate') / 100), 'Shortage: items not delivered');
  perform _pack(p_order, 'Partial delivery accepted');
end $function$
;

CREATE OR REPLACE FUNCTION public.confirm_delivery(p_order uuid, p_code text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare o orders; dc delivery_codes; v_max int := setting_num('delivery_code_max_attempts')::int;
begin
  perform _require('driver');
  if not is_my_delivery(p_order) then perform _err('This delivery is not assigned to you.'); end if;
  select * into o from orders where id = p_order for update;
  if o.status <> 'out_for_delivery' then perform _err('Confirm pickup first.'); end if;
  select * into dc from delivery_codes where order_id = p_order for update;
  if dc.order_id is null then perform _err('No code on this order. Call the Ops Desk.'); end if;
  if dc.locked then
    return jsonb_build_object('ok', false, 'locked', true, 'attempts_left', 0, 'message', 'Code locked after too many wrong attempts. The Ops Desk has been alerted.');
  end if;
  if dc.expires_at < now() then
    perform _notify_role('ops', 'code_expired', 'Delivery code expired: ' || o.order_no, 'Re-issue the code.', p_order, '/ops/alerts');
    return jsonb_build_object('ok', false, 'expired', true, 'message', 'This code has expired. The Ops Desk has been asked to re-issue it.');
  end if;

  if extensions.crypt(trim(coalesce(p_code,'')), dc.code_hash) = dc.code_hash then
    update delivery_codes set used_at = now() where order_id = p_order;
    update deliveries set delivered_at = now(), outcome = 'delivered' where order_id = p_order and current;
    perform _transition(p_order, 'delivered', 'Delivery code accepted');
    perform _notify_customer(o.customer_id, 'delivered', 'Delivered: ' || o.order_no, 'Thank you. Your order was delivered.', p_order, '/orders/' || p_order, true);
    perform _notify_role('ops', 'delivered', 'Delivered: ' || o.order_no, null, p_order, '/ops/orders/' || p_order);
    perform _notify_role('finance', 'delivered', 'Delivered: ' || o.order_no, null, p_order, null);
    perform _notify_role('dispatch', 'delivered', 'Delivered: ' || o.order_no, null, p_order, '/dispatch');
    return jsonb_build_object('ok', true);
  end if;

  update delivery_codes set failed_attempts = failed_attempts + 1, locked = (failed_attempts + 1 >= v_max)
  where order_id = p_order returning * into dc;
  perform audit('delivery_code', p_order::text, 'wrong_code', null, jsonb_build_object('attempt', dc.failed_attempts));
  if dc.locked then
    perform _notify_role('ops', 'code_locked', 'Delivery code locked: ' || o.order_no,
      'Too many wrong codes at the door. Re-issue the code or apply an override.', p_order, '/ops/alerts');
    perform _notify_role('dispatch', 'code_locked', 'Delivery code locked: ' || o.order_no, null, p_order, '/dispatch');
  end if;
  return jsonb_build_object('ok', false, 'locked', dc.locked, 'attempts_left', greatest(v_max - dc.failed_attempts, 0),
                            'message', case when dc.locked then 'Code locked. The Ops Desk has been alerted.' else 'Wrong code. Ask the customer to check it.' end);
end $function$
;

CREATE OR REPLACE FUNCTION public.confirm_payment(p_payment uuid)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare pay payments; inv invoices;
begin
  perform _require('finance');
  select * into pay from payments where id = p_payment for update;
  if pay.status <> 'pending' then perform _err('This payment has already been decided.'); end if;
  select * into inv from invoices where id = pay.invoice_id for update;
  update payments set status = 'confirmed', verified_by = auth.uid(), verified_at = now() where id = p_payment;
  update invoices set status = 'paid' where id = inv.id;
  perform _transition(inv.order_id, 'paid', 'Payment confirmed by Finance');
  perform audit('payment', p_payment::text, 'confirmed', null, jsonb_build_object('amount', pay.amount, 'reference', pay.reference));
  perform _notify_customer(inv.customer_id, 'payment_confirmed', 'Payment confirmed: ' || inv.invoice_no,
    'We have received your payment. Your order is being prepared.', inv.order_id, '/orders/' || inv.order_id, true);
  perform _notify_role('warehouse', 'ready_to_pick', 'Ready to pick: ' || _order_no(inv.order_id),
    'Paid and added to the pick list.', inv.order_id, '/warehouse/pick');
end $function$
;

CREATE OR REPLACE FUNCTION public.confirm_pickup(p_order uuid)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare o orders;
begin
  perform _require('driver');
  if not is_my_delivery(p_order) then perform _err('This delivery is not assigned to you.'); end if;
  select * into o from orders where id = p_order for update;
  if o.status <> 'assigned' then perform _err('This order is not waiting for pickup.'); end if;
  update deliveries set picked_up_at = now() where order_id = p_order and current;
  perform _transition(p_order, 'out_for_delivery', 'Driver confirmed pickup');
  perform _notify_customer(o.customer_id, 'out_for_delivery', 'Out for delivery: ' || o.order_no,
    'Your order is on the way. Your delivery code is on your dashboard; give it to the driver at handover.',
    p_order, '/codes', true);
end $function$
;

CREATE OR REPLACE FUNCTION public.decide_registration(p_customer uuid, p_decision text, p_note text, p_terms jsonb DEFAULT '{}'::jsonb)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare c customers; v_title text; v_body text;
begin
  perform _require('admin');
  select * into c from customers where id = p_customer for update;
  if c.id is null then perform _err('Customer not found.'); end if;
  if p_decision in ('reject','more_info') and trim(coalesce(p_note,'')) = '' then
    perform _err('A note for the applicant is required.');
  end if;

  if p_decision = 'accept' then
    update customers set status = 'active',
      payment_terms = coalesce(p_terms->>'payment_terms', setting('default_payment_terms') #>> '{}'),
      credit_limit = coalesce((p_terms->>'credit_limit')::numeric, setting_num('default_credit_limit')),
      allowed_region_ids = coalesce(array(select jsonb_array_elements_text(p_terms->'allowed_region_ids')::int), '{}'),
      trusted = coalesce((p_terms->>'trusted')::boolean, false),
      admin_note = p_note, rejection_reason = null, reapply_after = null
    where id = p_customer;
    v_title := 'Your account is active'; v_body := 'Your application was accepted. Sign in to place orders.';
  elsif p_decision = 'reject' then
    update customers set status = 'rejected', rejection_reason = p_note,
      reapply_after = current_date + setting_num('reapply_wait_days')::int
    where id = p_customer;
    v_title := 'Application not accepted'; v_body := p_note;
  elsif p_decision = 'hold' then
    update customers set status = 'on_hold', admin_note = p_note where id = p_customer;
    v_title := 'Application on hold'; v_body := coalesce(p_note, 'Your application is on hold. We will contact you.');
  elsif p_decision = 'more_info' then
    update customers set status = 'more_info', admin_note = p_note where id = p_customer;
    v_title := 'More information needed'; v_body := p_note;
  else
    perform _err('Unknown decision.');
  end if;

  update registration_applications set decision = p_decision, decided_by = auth.uid(), decided_at = now(), note = p_note
  where id = (select id from registration_applications where customer_id = p_customer order by created_at desc limit 1);
  perform audit('customer', p_customer::text, 'registration_' || p_decision,
                jsonb_build_object('status', c.status), jsonb_build_object('note', p_note, 'terms', p_terms));
  perform _notify_customer(p_customer, 'registration_' || p_decision, v_title, v_body, null, '/', true);
end $function$
;

CREATE OR REPLACE FUNCTION public.decline_cancel_request(p_order uuid, p_note text)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare o orders;
begin
  perform _require('ops');
  if trim(coalesce(p_note,'')) = '' then perform _err('Tell the customer why.'); end if;
  select * into o from orders where id = p_order for update;
  update orders set cancel_requested_reason = null where id = p_order;
  perform audit('order', p_order::text, 'cancel_declined', null, jsonb_build_object('note', p_note));
  perform _notify_customer(o.customer_id, 'cancel_declined', 'Cancellation not possible: ' || o.order_no, p_note, p_order, '/orders/' || p_order, true);
end $function$
;

CREATE OR REPLACE FUNCTION public.driver_deliveries()
 RETURNS jsonb
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
  select coalesce(jsonb_agg(jsonb_build_object(
    'order_id', o.id, 'order_no', o.order_no, 'status', o.status, 'requested_date', o.requested_date,
    'notes', o.notes, 'assigned_at', d.assigned_at, 'picked_up_at', d.picked_up_at,
    'customer', c.name, 'contact', c.contact_name, 'phone', c.phone,
    'address', a.line, 'region', r.name, 'instructions', a.instructions,
    'vehicle', v.plate,
    'attempts_left', greatest(setting_num('delivery_code_max_attempts')::int - coalesce(dc.failed_attempts, 0), 0),
    'code_locked', coalesce(dc.locked, false),
    'items', (select coalesce(jsonb_agg(jsonb_build_object('name', oi.product_name, 'sku', oi.product_sku, 'unit', oi.unit, 'qty', oi.qty_picked) order by oi.product_name), '[]')
              from order_items oi where oi.order_id = o.id and oi.qty_picked > 0)
  ) order by d.assigned_at), '[]')
  from deliveries d
  join orders o on o.id = d.order_id
  join customers c on c.id = o.customer_id
  left join addresses a on a.id = o.address_id
  left join regions r on r.id = a.region_id
  left join vehicles v on v.id = d.vehicle_id
  left join delivery_codes dc on dc.order_id = o.id
  where d.driver_id = auth.uid() and d.current and has_role('driver')
    and o.status in ('assigned','out_for_delivery')
$function$
;

CREATE OR REPLACE FUNCTION public.driver_history()
 RETURNS jsonb
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
  select coalesce(jsonb_agg(jsonb_build_object('order_no', o.order_no, 'customer', c.name, 'outcome', d.outcome,
    'failure_reason', d.failure_reason, 'at', coalesce(d.delivered_at, d.assigned_at)) order by d.assigned_at desc), '[]')
  from deliveries d join orders o on o.id = d.order_id join customers c on c.id = o.customer_id
  where d.driver_id = auth.uid() and not (d.current and o.status in ('assigned','out_for_delivery'))
    and d.assigned_at > now() - interval '14 days' and has_role('driver')
$function$
;

CREATE OR REPLACE FUNCTION public.expire_payment_windows()
 RETURNS integer
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare r record; n int := 0;
begin
  for r in select o.id, o.customer_id, o.order_no, i.id as invoice_id from orders o join invoices i on i.order_id = o.id
           where o.status in ('awaiting_payment','payment_rejected') and i.due_at < now() for update of o loop
    perform _release_reservation(r.id, 'Payment window expired');
    update invoices set status = 'expired' where id = r.invoice_id;
    update orders set cancel_reason = 'Payment window expired' where id = r.id;
    perform _transition(r.id, 'cancelled', 'Payment window expired');
    perform _notify_customer(r.customer_id, 'expired', 'Order cancelled: ' || r.order_no,
      'The payment window closed before payment was confirmed. Place a new order if you still need the items.', r.id, '/orders/' || r.id, true);
    n := n + 1;
  end loop;
  return n;
end $function$
;

CREATE OR REPLACE FUNCTION public.get_catalogue()
 RETURNS TABLE(id uuid, sku text, name text, unit text, price numeric, min_qty integer, max_qty integer, stock_status text, only_left integer)
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
  select p.id, p.sku, p.name, p.unit, p.price, p.min_qty, p.max_qty,
         case when p.on_hand - p.reserved <= 0 then 'out_of_stock'
              when p.on_hand - p.reserved <= setting_num('low_stock_warn_qty') then 'low_stock'
              else 'in_stock' end,
         (case when p.on_hand - p.reserved > 0 and p.on_hand - p.reserved <= setting_num('low_stock_warn_qty')
              then p.on_hand - p.reserved end)::int
  from products p
  where p.active and has_role('customer','ops','finance','warehouse','admin')
  order by p.name
$function$
;

CREATE OR REPLACE FUNCTION public.mark_notifications_read(p_ids bigint[] DEFAULT NULL::bigint[])
 RETURNS void
 LANGUAGE sql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
  update notifications set read_at = now()
  where user_id = auth.uid() and read_at is null and (p_ids is null or id = any(p_ids))
$function$
;

CREATE OR REPLACE FUNCTION public.mark_refund_paid(p_refund uuid, p_reference text)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare r refunds; v_cn text; o orders;
begin
  perform _require('finance');
  if trim(coalesce(p_reference,'')) = '' then perform _err('Enter the transfer reference.'); end if;
  select * into r from refunds where id = p_refund for update;
  if r.status <> 'requested' then perform _err('This refund has already been paid.'); end if;
  v_cn := 'CN-' || nextval('credit_note_seq');
  update refunds set status = 'paid', reference = trim(p_reference), paid_by = auth.uid(), paid_at = now(), credit_note_no = v_cn
  where id = p_refund;
  select * into o from orders where id = r.order_id;
  if o.status = 'cancelled' and _amount_refunded(r.order_id) >= _amount_paid(r.order_id) then
    update invoices set status = 'credited' where order_id = r.order_id;
  end if;
  perform audit('refund', p_refund::text, 'paid', null, jsonb_build_object('reference', p_reference, 'credit_note', v_cn));
  perform _notify_customer(r.customer_id, 'refund_paid', 'Refund paid: ' || o.order_no,
    format('%s refunded (credit note %s, reference %s).', r.amount, v_cn, trim(p_reference)), r.order_id, '/orders/' || r.order_id, true);
  perform _notify_role('ops', 'refund_paid', 'Refund paid: ' || o.order_no, format('%s, credit note %s', r.amount, v_cn), r.order_id, '/ops/refunds');
end $function$
;

CREATE OR REPLACE FUNCTION public.my_account()
 RETURNS jsonb
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
  select jsonb_build_object(
    'profile', to_jsonb(p) - 'created_at',
    'customer', (select to_jsonb(c) from customers c where c.id = my_customer_id()),
    'application', (select to_jsonb(a) - 'rule_results' from registration_applications a
                    where a.customer_id = my_customer_id() order by created_at desc limit 1),
    'email_confirmed', (select email_confirmed_at is not null from auth.users where id = auth.uid())
  )
  from profiles p where p.id = auth.uid()
$function$
;

CREATE OR REPLACE FUNCTION public.ops_cancel_order(p_order uuid, p_reason text)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare v_status order_status;
begin
  perform _require('ops');
  if trim(coalesce(p_reason,'')) = '' then perform _err('A reason is required.'); end if;
  select status into v_status from orders where id = p_order;
  if v_status in ('out_for_delivery','delivered','cancelled','delivery_failed') then
    perform _err('This order cannot be cancelled at this stage.');
  end if;
  perform _cancel(p_order, p_reason);
end $function$
;

CREATE OR REPLACE FUNCTION public.override_delivery(p_order uuid, p_reason text)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare o orders;
begin
  perform _require('ops');
  if length(trim(coalesce(p_reason,''))) < 10 then perform _err('Explain the override (at least 10 characters).'); end if;
  select * into o from orders where id = p_order for update;
  if o.status <> 'out_for_delivery' then perform _err('Only orders out for delivery can be overridden.'); end if;
  update deliveries set delivered_at = now(), outcome = 'override' where order_id = p_order and current;
  update delivery_codes set used_at = now() where order_id = p_order;
  perform _transition(p_order, 'delivered', 'OVERRIDE: ' || p_reason);
  perform audit('delivery', p_order::text, 'override', null, jsonb_build_object('reason', p_reason));
  perform _notify_customer(o.customer_id, 'delivered', 'Delivered: ' || o.order_no,
    'Your order was marked delivered by our Ops Desk. Contact us if this is wrong.', p_order, '/orders/' || p_order, true);
  perform _notify_role('admin', 'override', 'Delivery override: ' || o.order_no, p_reason, p_order, '/admin/audit');
end $function$
;

CREATE OR REPLACE FUNCTION public.password_changed()
 RETURNS void
 LANGUAGE sql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
  update profiles set must_change_password = false where id = auth.uid()
$function$
;

CREATE OR REPLACE FUNCTION public.performance_stats()
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare v jsonb;
begin
  perform _require('admin','ops');
  select jsonb_build_object(
    'orders_total', (select count(*) from orders where submitted_at is not null),
    'orders_by_status', (select coalesce(jsonb_object_agg(status, n), '{}') from (select status, count(*) n from orders group by status) s),
    'first_pass_rate', (
      select round(100.0 * count(*) filter (where first_to <> 'validation_failed') / nullif(count(*), 0), 1)
      from (select distinct on (order_id) order_id, to_status as first_to from order_events
            where from_status = 'submitted' order by order_id, at, id) f),
    'errors_by_rule', (select coalesce(jsonb_object_agg(rule, n), '{}') from
      (select vr.rule, count(*) n from validation_results vr join orders o on o.id = vr.order_id
       where vr.severity <> 'pass' and o.submitted_at is not null and vr.run_at <= coalesce(o.submitted_at, now()) + interval '1 second'
       group by vr.rule) r),
    'mandatory_missing', (select count(*) from orders where status not in ('draft','validation_failed','cancelled','rejected')
                          and submitted_at is not null and (address_id is null or requested_date is null
                          or not exists (select 1 from order_items oi where oi.order_id = orders.id and oi.qty_ordered > 0))),
    'avg_hours_by_stage', (select coalesce(jsonb_object_agg(from_status, hrs), '{}') from (
      select e.from_status, round(avg(extract(epoch from e.at - prev.at)) / 3600, 3) hrs
      from order_events e
      join lateral (select p.at from order_events p where p.order_id = e.order_id and p.id < e.id
                    order by p.id desc limit 1) prev on true
      where e.from_status is not null
      group by e.from_status) s),
    'avg_hours_submit_to_delivered', (
      select round(avg(extract(epoch from d.at - o.submitted_at)) / 3600, 2)
      from orders o join order_events d on d.order_id = o.id and d.to_status = 'delivered'),
    'auto_approved', (select count(*) from approvals where approver_id is null and decision = 'approved'),
    'manually_approved', (select count(*) from approvals where approver_id is not null and decision = 'approved'),
    'by_source', (select coalesce(jsonb_object_agg(source, n), '{}') from (select source, count(*) n from orders where submitted_at is not null group by source) s)
  ) into v;
  return v;
end $function$
;

CREATE OR REPLACE FUNCTION public.record_pick(p_order uuid, p_lines jsonb)
 RETURNS text
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare o orders; l jsonb; it order_items; v_found int; v_short boolean;
begin
  perform _require('warehouse');
  select * into o from orders where id = p_order for update;
  if o.status <> 'picking' then perform _err('Start picking first.'); end if;
  for l in select * from jsonb_array_elements(p_lines) loop
    select * into it from order_items where id = (l->>'item_id')::uuid and order_id = p_order for update;
    if it.id is null then perform _err('Line not on this order.'); end if;
    v_found := coalesce((l->>'qty_found')::int, 0);
    if v_found < 0 or v_found > it.qty_ordered - it.qty_picked then
      perform _err(format('Quantity found must be between 0 and %s.', it.qty_ordered - it.qty_picked));
    end if;
    if v_found > 0 then
      update products set on_hand = on_hand - v_found, reserved = greatest(reserved - least(v_found, it.qty_reserved), 0)
      where id = it.product_id;
      update order_items set qty_picked = qty_picked + v_found, qty_reserved = greatest(qty_reserved - v_found, 0) where id = it.id;
      insert into stock_movements (product_id, type, qty, reason, order_id, user_id)
      values (it.product_id, 'pick', v_found, 'Picked for ' || o.order_no, p_order, auth.uid());
      perform _check_low_stock(it.product_id);
    end if;
  end loop;

  select coalesce(bool_or(qty_picked < qty_ordered), false) into v_short from order_items where order_id = p_order;
  if not v_short then
    update orders set shortage_choice = null where id = p_order;
    perform _pack(p_order);
    return 'packed';
  end if;

  update orders set shortage_at = now(), shortage_choice = null where id = p_order;
  perform _transition(p_order, 'shortage_hold', 'Less stock found than ordered');
  perform _notify_role('ops', 'shortage', 'Shortage: ' || o.order_no,
    'The warehouse found less than ordered. The customer has been asked to choose.', p_order, '/ops/shortages');
  perform _notify_customer(o.customer_id, 'shortage', 'Action needed: ' || o.order_no,
    'Some items are short. Choose to receive what is available, wait for restock, or cancel.', p_order, '/orders/' || p_order, true);
  return 'shortage_hold';
end $function$
;

CREATE OR REPLACE FUNCTION public.reissue_code(p_order uuid, p_reason text)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare o orders;
begin
  perform _require('ops');
  if trim(coalesce(p_reason,'')) = '' then perform _err('A reason is required.'); end if;
  select * into o from orders where id = p_order for update;
  if o.status not in ('packed','assigned','out_for_delivery','delivery_failed') then
    perform _err('Codes can only be re-issued for packed orders not yet delivered.');
  end if;
  perform _issue_code(p_order);
  perform audit('delivery_code', p_order::text, 'reissued', null, jsonb_build_object('reason', p_reason));
  perform _notify_customer(o.customer_id, 'code_reissued', 'New delivery code: ' || o.order_no,
    'Your old code no longer works. The new one is on your dashboard.', p_order, '/codes', true);
end $function$
;

CREATE OR REPLACE FUNCTION public.reject_order(p_order uuid, p_reason text)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare o orders;
begin
  perform _require('ops');
  if trim(coalesce(p_reason,'')) = '' then perform _err('A reason is required.'); end if;
  select * into o from orders where id = p_order for update;
  if o.status <> 'pending_approval' then perform _err('Only orders waiting for approval can be rejected.'); end if;
  insert into approvals (order_id, approver_id, decision, comment) values (p_order, auth.uid(), 'rejected', p_reason);
  perform _transition(p_order, 'rejected', p_reason);
  perform _notify_customer(o.customer_id, 'rejected', 'Order rejected: ' || o.order_no,
    'Reason: ' || p_reason || '. You can edit and resubmit it.', p_order, '/orders/' || p_order, true);
end $function$
;

CREATE OR REPLACE FUNCTION public.reject_payment(p_payment uuid, p_reason text)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare pay payments; inv invoices; o orders; v_used int;
begin
  perform _require('finance');
  if trim(coalesce(p_reason,'')) = '' then perform _err('A reason is required.'); end if;
  select * into pay from payments where id = p_payment for update;
  if pay.status <> 'pending' then perform _err('This payment has already been decided.'); end if;
  select * into inv from invoices where id = pay.invoice_id for update;
  select * into o from orders where id = inv.order_id;
  update payments set status = 'rejected', verified_by = auth.uid(), verified_at = now(), reason = p_reason where id = p_payment;
  -- the window was paused while Finance checked; give the customer time to re-upload
  update invoices set due_at = greatest(due_at, now() + make_interval(hours => setting_num('payment_reupload_grace_hours')::int))
  where id = inv.id;
  perform _transition(inv.order_id, 'payment_rejected', p_reason);
  perform audit('payment', p_payment::text, 'rejected', null, jsonb_build_object('reason', p_reason));
  select count(*) into v_used from payments where invoice_id = inv.id;
  if v_used >= o.payment_attempts_allowed then
    perform _notify_customer(inv.customer_id, 'payment_rejected', 'Payment not accepted: ' || inv.invoice_no,
      'Reason: ' || p_reason || '. You have used all upload attempts; our Ops Desk will contact you.', inv.order_id, '/invoices', true);
    perform _notify_role('ops', 'payment_escalation', 'Payment attempts used up: ' || o.order_no,
      'Finance rejected the last allowed proof. Contact the customer.', inv.order_id, '/ops/alerts');
  else
    perform _notify_customer(inv.customer_id, 'payment_rejected', 'Payment not accepted: ' || inv.invoice_no,
      format('Reason: %s. Upload a new proof (%s of %s attempts used).', p_reason, v_used, o.payment_attempts_allowed),
      inv.order_id, '/invoices', true);
  end if;
end $function$
;

CREATE OR REPLACE FUNCTION public.remove_address(p_id uuid)
 RETURNS void
 LANGUAGE sql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
  update addresses set active = false where id = p_id and customer_id = my_customer_id()
$function$
;

CREATE OR REPLACE FUNCTION public.reorder(p_order uuid)
 RETURNS uuid
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare o orders;
begin
  select * into o from orders where id = p_order and customer_id = my_customer_id();
  if o.id is null then perform _err('Order not found.'); end if;
  return save_draft(null, jsonb_build_object(
    'address_id', o.address_id, 'source', 'reorder',
    'items', (select coalesce(jsonb_agg(jsonb_build_object('product_id', product_id, 'qty', qty_ordered)), '[]')
              from order_items where order_id = p_order and qty_ordered > 0)));
end $function$
;

CREATE OR REPLACE FUNCTION public.report_delivery_failed(p_order uuid, p_reason text)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare o orders;
begin
  perform _require('driver');
  if trim(coalesce(p_reason,'')) = '' then perform _err('Choose a reason.'); end if;
  if not is_my_delivery(p_order) then perform _err('This delivery is not assigned to you.'); end if;
  select * into o from orders where id = p_order for update;
  if o.status <> 'out_for_delivery' then perform _err('Only orders out for delivery can be marked failed.'); end if;
  update deliveries set outcome = 'failed', failure_reason = p_reason, current = false where order_id = p_order and current;
  perform _transition(p_order, 'delivery_failed', p_reason);
  perform _notify_role('dispatch', 'delivery_failed', 'Delivery failed: ' || o.order_no, p_reason || '. Reschedule it.', p_order, '/dispatch');
  perform _notify_role('ops', 'delivery_failed', 'Delivery failed: ' || o.order_no, p_reason, p_order, '/ops/alerts');
  perform _notify_customer(o.customer_id, 'delivery_failed', 'Delivery attempt failed: ' || o.order_no,
    'Reason: ' || p_reason || '. We will reschedule and let you know.', p_order, '/orders/' || p_order, true);
end $function$
;

CREATE OR REPLACE FUNCTION public.request_refund(p_order uuid, p_amount numeric, p_reason text)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
begin
  perform _require('ops');
  if trim(coalesce(p_reason,'')) = '' then perform _err('A reason is required.'); end if;
  if p_amount is null or p_amount <= 0 then perform _err('Enter an amount.'); end if;
  if p_amount > _amount_paid(p_order) - _amount_refunded(p_order) then
    perform _err('The amount is more than what was paid and not yet refunded.');
  end if;
  perform _raise_refund(p_order, p_amount, p_reason);
end $function$
;

CREATE OR REPLACE FUNCTION public.run_simulation(p_n integer DEFAULT 500, p_seed double precision DEFAULT 0.42)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  v_by uuid := auth.uid();
  claims text := current_setting('request.jwt.claims', true);
  cats text[] := array['clean','clean','clean','clean','clean','clean','clean','clean','clean','clean',
                       'bad_sku','missing_address','missing_date','past_date','qty_below_min','qty_above_max',
                       'fractional_qty','over_stock','duplicate','inactive_product',
                       'wrong_product','qty_typo','wrong_address'];
  targeted text[] := array['bad_sku','missing_address','missing_date','past_date','qty_below_min','qty_above_max',
                           'fractional_qty','over_stock','duplicate','inactive_product'];
  cust record; cat text; i int; o uuid; r jsonb; items jsonb; pr record; p2 record; addr uuid; addr2 uuid;
  v_date date; v_unm jsonb; outcome text; log jsonb := '[]'; last_items jsonb := null; last_cust text := null; last_items_cust text := null;
  summary jsonb; result jsonb;
begin
  if not has_role('admin') then perform _err('Only an administrator can run the simulation.'); end if;
  if p_n < 10 or p_n > 2000 then perform _err('Choose between 10 and 2000 orders.'); end if;
  perform setseed(p_seed);
  begin
    update settings set value = 'false' where key = 'auto_approve_enabled';
    update products set active = false where sku = 'SAND-T';

    -- a little order history per customer so the unusual-quantity rule has something to compare with
    for cust in select p.email from profiles p join customer_users cu on cu.user_id = p.id join customers c on c.id = cu.customer_id where c.status = 'active' loop
      perform _as(cust.email);
      addr := (select id from addresses where customer_id = my_customer_id() and active order by label limit 1);
      for i in 1..4 loop
        o := save_draft(null, jsonb_build_object('address_id', addr, 'requested_date', current_date + 3, 'source', 'simulation',
               'items', jsonb_build_array(jsonb_build_object('product_id', (select id from products where sku='CEM-50'), 'qty', 20 + i),
                                          jsonb_build_object('product_id', (select id from products where sku='ROD-12'), 'qty', 10 + i))));
        perform submit_order(o, true);
      end loop;
    end loop;

    for i in 1..p_n loop
      cat := cats[1 + floor(random() * array_length(cats, 1))::int];
      select pe.email into last_cust from profiles pe join customer_users cu on cu.user_id = pe.id join customers c on c.id = cu.customer_id
        where c.status = 'active' order by random() limit 1;
      perform _as(last_cust);
      addr := (select id from addresses where customer_id = my_customer_id() and active order by random() limit 1);
      v_date := current_date + 1 + floor(random() * 10)::int;
      v_unm := '[]';
      -- 1 to 3 clean lines within limits and stock
      items := '[]';
      for pr in select * from products where active and on_hand - reserved >= min_qty * 3 order by random() limit 1 + floor(random() * 3)::int loop
        items := items || jsonb_build_array(jsonb_build_object('product_id', pr.id,
                   'qty', pr.min_qty + floor(random() * least(pr.max_qty - pr.min_qty, greatest((pr.on_hand - pr.reserved) / 4 - pr.min_qty, 1)))::int));
      end loop;

      if cat = 'bad_sku' then v_unm := jsonb_build_array(jsonb_build_object('row', 3, 'sku', 'XX-' || (100 + floor(random()*900))::int, 'problem', 'not in the catalogue'));
      elsif cat = 'missing_address' then addr := null;
      elsif cat = 'missing_date' then v_date := null;
      elsif cat = 'past_date' then v_date := current_date - 1 - floor(random() * 5)::int;
      elsif cat in ('qty_below_min','qty_above_max','over_stock','fractional_qty') then
        select * into p2 from products where active and sku <> 'SAND-T' and min_qty > 1
       and not (id::text in (select x->>'product_id' from jsonb_array_elements(items) x)) order by random() limit 1;
        items := items || jsonb_build_array(jsonb_build_object('product_id', p2.id, 'qty',
          case cat when 'qty_below_min' then p2.min_qty - 1
                   when 'qty_above_max' then p2.max_qty + 1 + floor(random() * 50)::int
                   when 'over_stock' then least(p2.max_qty, greatest(p2.on_hand - p2.reserved + 1, p2.min_qty))
                   else p2.min_qty + 0.5 end));
        if cat = 'over_stock' and least(p2.max_qty, greatest(p2.on_hand - p2.reserved + 1, p2.min_qty)) <= p2.on_hand - p2.reserved then
          cat := 'clean'; -- cannot exceed stock within the max limit for this product
        end if;
      elsif cat = 'inactive_product' then
        items := items || jsonb_build_array(jsonb_build_object('product_id', (select id from products where sku='SAND-T'), 'qty', 1));
      elsif cat = 'duplicate' then
        if last_items is not null then
          perform _as(last_items_cust);
          items := last_items;
          addr := (select id from addresses where customer_id = my_customer_id() and active order by label limit 1);
          last_cust := last_items_cust;
        else cat := 'clean'; end if;
      elsif cat = 'wrong_product' then
        -- customer meant one product but picked its neighbour: a valid order, wrong intent
        select * into p2 from products where sku = (array['ROD-16','ROD-12','PNT-20C','PNT-20W','PVC-2','PVC-4'])[1 + floor(random()*6)::int];
        items := jsonb_build_array(jsonb_build_object('product_id', p2.id, 'qty', least(p2.min_qty + floor(random() * 20)::int, greatest(p2.on_hand - p2.reserved, p2.min_qty))));
      elsif cat = 'qty_typo' then
        -- typed 200 instead of 20: still inside the limits and stock
        items := jsonb_build_array(jsonb_build_object('product_id', (select id from products where sku = 'CEM-50'), 'qty', 200 + floor(random()*20)::int));
      elsif cat = 'wrong_address' then
        addr := (select id from addresses where customer_id = my_customer_id() and active order by label desc limit 1);
      end if;

      o := save_draft(null, jsonb_build_object('address_id', addr, 'requested_date', v_date, 'source', 'simulation', 'items', items, 'unmatched', v_unm));
      r := submit_order(o, false);
      outcome := case when (r->>'needs_confirmation')::boolean then 'warn' else r->>'outcome' end;
      log := log || jsonb_build_array(jsonb_build_object('cat', cat, 'outcome', outcome, 'cust', last_cust,
                'rules', (select coalesce(jsonb_agg(distinct x->>'rule'), '[]') from jsonb_array_elements(r->'results') x where x->>'severity' <> 'pass')));
      if cat = 'clean' and outcome = 'pass' then last_items := items; last_items_cust := last_cust; end if;
    end loop;
    raise exception 'SIM_ROLLBACK';
  exception when others then
    if sqlerrm <> 'SIM_ROLLBACK' then raise; end if;
  end;
  perform set_config('request.jwt.claims', claims, true);

  select jsonb_build_object(
    'total', count(*),
    'by_category', (select jsonb_object_agg(category, jsonb_build_object('n', n, 'flagged', f, 'blocked', b)) from (
        select e->>'cat' category, count(*) n, count(*) filter (where e->>'outcome' in ('fail','warn')) f, count(*) filter (where e->>'outcome' = 'fail') b
        from jsonb_array_elements(log) e group by 1) s),
    'clean', count(*) filter (where e->>'cat' = 'clean'),
    'clean_passed', count(*) filter (where e->>'cat' = 'clean' and e->>'outcome' = 'pass'),
    'targeted', count(*) filter (where e->>'cat' = any(targeted)),
    'targeted_caught', count(*) filter (where e->>'cat' = any(targeted) and e->>'outcome' in ('fail','warn')),
    'untargeted', count(*) filter (where e->>'cat' <> 'clean' and not (e->>'cat' = any(targeted))),
    'untargeted_caught', count(*) filter (where e->>'cat' <> 'clean' and not (e->>'cat' = any(targeted)) and e->>'outcome' in ('fail','warn')),
    'mandatory_complete', 100
  ) into summary from jsonb_array_elements(log) e;

  summary := summary || jsonb_build_object(
    'accuracy_targeted', round(100.0 * ((summary->>'targeted_caught')::int + (summary->>'clean_passed')::int) / nullif((summary->>'targeted')::int + (summary->>'clean')::int, 0), 1),
    'accuracy_all', round(100.0 * ((summary->>'targeted_caught')::int + (summary->>'untargeted_caught')::int + (summary->>'clean_passed')::int) / nullif((summary->>'total')::int, 0), 1));

  insert into simulation_runs (run_by, orders, summary) values (v_by, p_n, summary);
  return summary;
end $function$
;

CREATE OR REPLACE FUNCTION public.save_address(p_id uuid, p_label text, p_line text, p_region integer, p_instructions text)
 RETURNS uuid
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare v_cust uuid := my_customer_id(); v_id uuid;
begin
  if v_cust is null then perform _err('No customer account.'); end if;
  if trim(coalesce(p_label,'')) = '' or trim(coalesce(p_line,'')) = '' or p_region is null then
    perform _err('Label, address and region are required.');
  end if;
  if p_id is null then
    insert into addresses (customer_id, label, line, region_id, instructions)
    values (v_cust, trim(p_label), trim(p_line), p_region, p_instructions) returning id into v_id;
  else
    update addresses set label = trim(p_label), line = trim(p_line), region_id = p_region, instructions = p_instructions
    where id = p_id and customer_id = v_cust returning id into v_id;
    if v_id is null then perform _err('Address not found.'); end if;
  end if;
  return v_id;
end $function$
;

CREATE OR REPLACE FUNCTION public.save_draft(p_order uuid, p jsonb)
 RETURNS uuid
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  v_cust uuid := my_customer_id();
  v_status customer_status;
  v_id uuid := p_order;
  v_cur order_status;
  it record;
  v_bad jsonb := '[]';
begin
  if v_cust is null then perform _err('No customer account.'); end if;
  select status into v_status from customers where id = v_cust;
  if v_status <> 'active' then perform _err('Your account is not active, so you cannot place orders.'); end if;

  if v_id is null then
    insert into orders (customer_id, source, created_by)
    values (v_cust, coalesce(nullif(p->>'source',''), 'portal'), auth.uid())
    returning id into v_id;
    insert into order_events (order_id, from_status, to_status, user_id) values (v_id, null, 'draft', auth.uid());
  else
    select status into v_cur from orders where id = v_id and customer_id = v_cust for update;
    if v_cur is null then perform _err('Order not found.'); end if;
    if v_cur not in ('draft','validation_failed','rejected') then
      perform _err('This order can no longer be edited.');
    end if;
  end if;

  -- lines removed from the form keep their row with quantity 0 and are ignored everywhere
  update order_items set qty_ordered = 0 where order_id = v_id;

  for it in
    select (x->>'product_id')::uuid as product_id, sum(nullif(x->>'qty','')::numeric) as qty
    from jsonb_array_elements(coalesce(p->'items','[]')) x group by 1
  loop
    if it.qty is null or it.qty <> trunc(it.qty) or it.qty <= 0 then
      v_bad := v_bad || jsonb_build_array(jsonb_build_object(
        'sku', (select sku from products where id = it.product_id), 'qty', it.qty,
        'problem', case when it.qty is null or it.qty <> trunc(it.qty) then 'Quantity must be a whole number'
                        else 'Quantity must be more than 0' end));
      continue;
    end if;
    insert into order_items (order_id, product_id, qty_ordered, unit_price)
    select v_id, pr.id, it.qty::int, pr.price from products pr where pr.id = it.product_id
    on conflict (order_id, product_id) do update set qty_ordered = excluded.qty_ordered, unit_price = excluded.unit_price;
  end loop;

  update orders set
    address_id = nullif(p->>'address_id','')::uuid,
    requested_date = nullif(p->>'requested_date','')::date,
    notes = nullif(p->>'notes',''),
    unmatched_lines = coalesce(p->'unmatched', '[]') || v_bad,
    duplicate_confirmed = false,
    updated_at = now()
  where id = v_id;

  perform _recalc_order(v_id);
  return v_id;
end $function$
;

CREATE OR REPLACE FUNCTION public.scheduled_alerts()
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare r record;
begin
  for r in select o.id, o.customer_id, o.order_no, i.due_at from orders o join invoices i on i.order_id = o.id
           where o.status in ('awaiting_payment','payment_rejected') and i.due_at between now() and now() + interval '6 hours'
             and not exists (select 1 from notifications n where n.order_id = o.id and n.event = 'payment_due_soon') loop
    perform _notify_customer(r.customer_id, 'payment_due_soon', 'Payment due soon: ' || r.order_no,
      'Your payment window closes at ' || to_char(r.due_at at time zone 'Africa/Lagos', 'HH24:MI DD Mon') || '.', r.id, '/invoices', true);
  end loop;
  for r in select o.id, o.order_no from orders o
           where o.status = 'shortage_hold' and o.shortage_choice = 'wait_restock'
             and o.shortage_at < now() - make_interval(days => setting_num('restock_wait_days')::int)
             and not exists (select 1 from notifications n where n.order_id = o.id and n.event = 'restock_overdue') loop
    perform _notify_role('ops', 'restock_overdue', 'Restock overdue: ' || r.order_no,
      'The customer has waited longer than the restock limit. Contact them.', r.id, '/ops/shortages');
  end loop;
end $function$
;

CREATE OR REPLACE FUNCTION public.set_customer_status(p_customer uuid, p_status customer_status, p_note text)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare v_old customer_status;
begin
  perform _require('admin');
  if trim(coalesce(p_note,'')) = '' then perform _err('A reason is required.'); end if;
  select status into v_old from customers where id = p_customer for update;
  update customers set status = p_status, admin_note = p_note where id = p_customer;
  perform audit('customer', p_customer::text, 'status_change', jsonb_build_object('status', v_old),
                jsonb_build_object('status', p_status, 'note', p_note));
  perform _notify_customer(p_customer, 'account_status', 'Account status changed', p_note, null, '/', true);
end $function$
;

CREATE OR REPLACE FUNCTION public.start_picking(p_order uuid)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare v_status order_status;
begin
  perform _require('warehouse');
  select status into v_status from orders where id = p_order;
  if v_status not in ('paid','shortage_hold') then perform _err('Only paid orders (or orders waiting for restock) can be picked.'); end if;
  if v_status = 'shortage_hold' and (select shortage_choice from orders where id = p_order) is distinct from 'wait_restock' then
    perform _err('The customer has not chosen to wait for restock.');
  end if;
  perform _transition(p_order, 'picking', case when v_status = 'shortage_hold' then 'Resumed after restock' end);
end $function$
;

CREATE OR REPLACE FUNCTION public.stock_in(p_product uuid, p_qty integer, p_reference text, p_reason text)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare r record; v_name text;
begin
  perform _require('warehouse');
  if p_qty is null or p_qty <= 0 then perform _err('Quantity must be more than 0.'); end if;
  if trim(coalesce(p_reference,'')) = '' then perform _err('Enter a reference (delivery note, PO number).'); end if;
  update products set on_hand = on_hand + p_qty where id = p_product returning name into v_name;
  if v_name is null then perform _err('Product not found.'); end if;
  insert into stock_movements (product_id, type, qty, reason, reference, user_id)
  values (p_product, 'in', p_qty, coalesce(nullif(trim(p_reason),''), 'Stock received'), trim(p_reference), auth.uid());
  for r in select distinct o.id, o.order_no from orders o join order_items oi on oi.order_id = o.id
           where o.status = 'shortage_hold' and o.shortage_choice = 'wait_restock'
             and oi.product_id = p_product and oi.qty_picked < oi.qty_ordered loop
    perform _notify_role('warehouse', 'restock_arrived', 'Restock for ' || r.order_no, v_name || ' arrived. Resume picking.', r.id, '/warehouse/pick');
    perform _notify_role('ops', 'restock_arrived', 'Restock for ' || r.order_no, v_name || ' arrived.', r.id, '/ops/shortages');
  end loop;
end $function$
;

CREATE OR REPLACE FUNCTION public.submit_order(p_order uuid, p_confirm_duplicate boolean DEFAULT false)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  o orders; c customers; v jsonb; v_auto boolean;
begin
  select * into o from orders where id = p_order and customer_id = my_customer_id() for update;
  if o.id is null then perform _err('Order not found.'); end if;
  if o.status not in ('draft','validation_failed','rejected') then perform _err('This order has already been submitted.'); end if;
  select * into c from customers where id = o.customer_id;

  if p_confirm_duplicate then update orders set duplicate_confirmed = true where id = p_order; end if;
  perform _recalc_order(p_order);
  select * into o from orders where id = p_order;

  v := _validate(p_order);
  if (v->>'outcome') <> 'fail' and (v->>'duplicate_unconfirmed')::boolean then
    return v || jsonb_build_object('status', o.status, 'needs_confirmation', true);
  end if;

  update orders set submitted_at = now() where id = p_order;
  perform _transition(p_order, 'submitted');

  if (v->>'outcome') = 'fail' then
    perform _transition(p_order, 'validation_failed', 'Blocking rule failed');
    return v || jsonb_build_object('status', 'validation_failed');
  end if;

  v_auto := (setting('auto_approve_enabled') #>> '{}')::boolean
            and (v->>'outcome') = 'pass'
            and c.payment_terms = 'prepaid'
            and o.total <= setting_num('auto_approve_max_total');

  if v_auto then
    begin
      perform _approve(p_order, 'Auto-approved: passed every rule with no warnings');
      return v || jsonb_build_object('status', 'awaiting_payment', 'auto_approved', true);
    exception when sqlstate 'P0001' then
      v := _validate(p_order);
      perform _transition(p_order, 'validation_failed', 'Stock changed during approval');
      return v || jsonb_build_object('status', 'validation_failed');
    end;
  end if;

  perform _transition(p_order, 'pending_approval', case when (v->>'outcome') = 'warn' then 'Passed with warnings' end);
  perform _notify_role('ops', 'order_submitted', 'To approve: ' || o.order_no,
    format('%s, total %s%s', c.name, o.total, case when (v->>'outcome') = 'warn' then ' (has warnings)' else '' end),
    p_order, '/ops/approvals');
  perform _notify_customer(o.customer_id, 'submitted', 'Order submitted: ' || o.order_no,
    'Your order passed validation and is under review.', p_order, '/orders/' || p_order);
  return v || jsonb_build_object('status', 'pending_approval');
end $function$
;

CREATE OR REPLACE FUNCTION public.submit_registration(p jsonb)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  v_uid uuid := auth.uid();
  v_email text; v_domain text; v_confirmed boolean;
  v_existing customers;
  v_cust uuid;
  v_results jsonb := '[]';
  v_outcome text := 'manual_review';
  v_status customer_status := 'awaiting_review';
  v_reason text;
  v_docs text[] := coalesce(array(select jsonb_array_elements_text(p->'documents')), '{}');
  v_reg text := trim(coalesce(p->>'reg_no', ''));
  f text;
begin
  if v_uid is null then perform _err('Sign in first.'); end if;
  if my_role() is distinct from 'customer' then perform _err('Staff accounts cannot register a company.'); end if;
  select email, email_confirmed_at is not null into v_email, v_confirmed from auth.users where id = v_uid;
  if not v_confirmed then perform _err('Verify your e-mail address before submitting.'); end if;
  v_domain := lower(split_part(v_email, '@', 2));

  select c.* into v_existing from customers c join customer_users cu on cu.customer_id = c.id where cu.user_id = v_uid;
  if v_existing.id is not null then
    if v_existing.status not in ('more_info','rejected') then
      perform _err('Your application has already been submitted.');
    end if;
    if v_existing.status = 'rejected' and v_existing.reapply_after > current_date then
      perform _err(format('You can reapply from %s.', to_char(v_existing.reapply_after, 'DD Mon YYYY')));
    end if;
  end if;

  foreach f in array array['name','reg_no','contact_name','phone','address'] loop
    if trim(coalesce(p->>f, '')) = '' then
      perform _err(format('%s is required.', initcap(replace(f, '_', ' '))));
    end if;
  end loop;
  if (setting('require_documents') #>> '{}')::boolean and coalesce(array_length(v_docs, 1), 0) = 0 then
    perform _err('Attach your business registration certificate.');
  end if;
  if exists (select 1 from unnest(v_docs) d where split_part(d, '/', 1) <> v_uid::text) then
    perform _err('Upload the documents again.');
  end if;
  v_results := v_results || jsonb_build_object('rule','required_fields','result','pass','message','All required fields and documents present');

  if exists (select 1 from customers where lower(reg_no) = lower(v_reg) and id is distinct from v_existing.id) then
    perform _err('A company with this registration number already has an account. Contact us if you need access.');
  end if;
  v_results := v_results || jsonb_build_object('rule','duplicate','result','pass','message','No existing customer with this registration number');

  if exists (select 1 from screening_list where (kind = 'blocked_reg_no' and lower(value) = lower(v_reg))
                                            or (kind = 'blocked_email' and lower(value) = lower(v_email))
                                            or (kind = 'blocked_domain' and lower(value) = v_domain)) then
    v_outcome := 'auto_rejected'; v_status := 'rejected';
    v_reason := 'The application did not pass our screening checks.';
    v_results := v_results || jsonb_build_object('rule','blocked_list','result','fail','message','Matches the blocked list');
  else
    v_results := v_results || jsonb_build_object('rule','blocked_list','result','pass','message','Not on the blocked list');
  end if;

  if v_outcome <> 'auto_rejected' and exists (select 1 from screening_list where kind = 'free_domain' and lower(value) = v_domain) then
    if (setting('reject_free_domains') #>> '{}')::boolean then
      v_outcome := 'auto_rejected'; v_status := 'rejected';
      v_reason := 'Register with your company e-mail address, not a free e-mail service.';
      v_results := v_results || jsonb_build_object('rule','free_domain','result','fail','message','Free e-mail domain ' || v_domain);
    else
      v_results := v_results || jsonb_build_object('rule','free_domain','result','warn','message','Free e-mail domain ' || v_domain);
    end if;
  end if;

  if v_outcome <> 'auto_rejected' then
    if coalesce(nullif(p->>'expected_volume','')::int, 0) > setting_num('manual_review_volume') then
      v_results := v_results || jsonb_build_object('rule','volume','result','warn','message','Expected volume above review threshold');
    elsif exists (select 1 from screening_list where kind = 'preapproved_reg_no' and lower(value) = lower(v_reg)) then
      v_outcome := 'auto_approved'; v_status := 'active';
      v_results := v_results || jsonb_build_object('rule','preapproved','result','pass','message','Registration number is pre-approved');
    end if;
  end if;

  if v_existing.id is null then
    insert into customers (name, reg_no, contact_name, email, phone, address, industry, expected_volume, status,
                           payment_terms, credit_limit, rejection_reason, reapply_after)
    values (trim(p->>'name'), v_reg, trim(p->>'contact_name'), v_email, trim(p->>'phone'), trim(p->>'address'),
            nullif(trim(coalesce(p->>'industry','')), ''), nullif(p->>'expected_volume','')::int, v_status,
            setting('default_payment_terms') #>> '{}', setting_num('default_credit_limit'), v_reason,
            case when v_status = 'rejected' then current_date + setting_num('reapply_wait_days')::int end)
    returning id into v_cust;
    insert into customer_users (user_id, customer_id) values (v_uid, v_cust);
  else
    v_cust := v_existing.id;
    update customers set name = trim(p->>'name'), reg_no = v_reg, contact_name = trim(p->>'contact_name'),
      phone = trim(p->>'phone'), address = trim(p->>'address'),
      industry = nullif(trim(coalesce(p->>'industry','')), ''), expected_volume = nullif(p->>'expected_volume','')::int,
      status = v_status, rejection_reason = v_reason, admin_note = null,
      reapply_after = case when v_status = 'rejected' then current_date + setting_num('reapply_wait_days')::int end
    where id = v_cust;
  end if;

  update profiles set full_name = coalesce(nullif(trim(p->>'contact_name'), ''), full_name), phone = trim(p->>'phone')
  where id = v_uid;

  insert into registration_applications (customer_id, rule_results, documents, outcome)
  values (v_cust, v_results, v_docs, case when v_existing.id is not null and v_outcome = 'manual_review' then 'resubmitted' else v_outcome end);
  perform audit('customer', v_cust::text, 'registration_' || v_outcome, null, jsonb_build_object('results', v_results));

  if v_outcome = 'manual_review' then
    perform _notify_role('admin', 'registration_received', 'New registration: ' || trim(p->>'name'),
                         'An application is waiting for review.', null, '/admin/registrations');
    perform _notify_user(v_uid, 'registration_received', 'Application received',
                         'We are reviewing your application and will e-mail you with the decision.', null, '/', true);
  elsif v_outcome = 'auto_approved' then
    perform _notify_user(v_uid, 'registration_accepted', 'Your account is active',
                         'You can now place orders.', null, '/', true);
  else
    perform _notify_user(v_uid, 'registration_rejected', 'Application not accepted', v_reason, null, '/', true);
  end if;

  return jsonb_build_object('customer_id', v_cust, 'outcome', v_outcome, 'status', v_status);
end $function$
;

CREATE OR REPLACE FUNCTION public.touch_login()
 RETURNS void
 LANGUAGE sql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
  update profiles set last_login = now() where id = auth.uid()
$function$
;

CREATE OR REPLACE FUNCTION public.unassign_delivery(p_order uuid, p_reason text)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare v_driver uuid;
begin
  perform _require('dispatch');
  if trim(coalesce(p_reason,'')) = '' then perform _err('A reason is required.'); end if;
  if (select status from orders where id = p_order) is distinct from 'assigned' then
    perform _err('Only assigned orders that are not yet picked up can be unassigned.');
  end if;
  update deliveries set current = false, outcome = 'reassigned', failure_reason = p_reason
  where order_id = p_order and current returning driver_id into v_driver;
  perform _transition(p_order, 'packed', 'Unassigned: ' || p_reason);
  if v_driver is not null then
    perform _notify_user(v_driver, 'unassigned', 'Delivery removed: ' || _order_no(p_order), p_reason, null, '/driver');
  end if;
end $function$
;

CREATE OR REPLACE FUNCTION public.update_customer_terms(p_customer uuid, p_terms jsonb)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare c customers;
begin
  perform _require('admin');
  select * into c from customers where id = p_customer;
  update customers set
    payment_terms = coalesce(p_terms->>'payment_terms', payment_terms),
    credit_limit = coalesce((p_terms->>'credit_limit')::numeric, credit_limit),
    allowed_region_ids = case when p_terms ? 'allowed_region_ids'
                              then array(select jsonb_array_elements_text(p_terms->'allowed_region_ids')::int)
                              else allowed_region_ids end,
    trusted = coalesce((p_terms->>'trusted')::boolean, trusted)
  where id = p_customer;
  perform audit('customer', p_customer::text, 'terms_change', to_jsonb(c), p_terms);
end $function$
;

CREATE OR REPLACE FUNCTION public.update_my_profile(p_full_name text, p_phone text)
 RETURNS void
 LANGUAGE sql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
  update profiles set full_name = p_full_name, phone = p_phone where id = auth.uid()
$function$
;

CREATE OR REPLACE FUNCTION public.upload_payment(p_invoice uuid, p_amount numeric, p_reference text, p_proof_path text)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare inv invoices; o orders; v_n int;
begin
  select * into inv from invoices where id = p_invoice and customer_id = my_customer_id() for update;
  if inv.id is null then perform _err('Invoice not found.'); end if;
  select * into o from orders where id = inv.order_id for update;
  if o.status not in ('awaiting_payment','payment_rejected') then perform _err('This invoice is not waiting for payment.'); end if;
  if inv.due_at < now() then perform _err('The payment window has closed.'); end if;
  if trim(coalesce(p_reference,'')) = '' then perform _err('Enter the transfer reference.'); end if;
  if p_amount is null or p_amount <= 0 then perform _err('Enter the amount you paid.'); end if;
  if p_proof_path is not null and split_part(p_proof_path, '/', 1) <> auth.uid()::text then
    perform _err('Upload the proof file again.');
  end if;
  select count(*) into v_n from payments where invoice_id = p_invoice;
  if v_n >= o.payment_attempts_allowed then
    perform _err('You have used all upload attempts. The Ops Desk will contact you.');
  end if;
  insert into payments (invoice_id, customer_id, amount, reference, proof_path, attempt_no, uploaded_by)
  values (p_invoice, inv.customer_id, p_amount, trim(p_reference), p_proof_path, v_n + 1, auth.uid());
  perform _transition(o.id, 'payment_verification', format('Proof uploaded (attempt %s)', v_n + 1));
  perform _notify_role('finance', 'payment_uploaded', 'Payment to verify: ' || inv.invoice_no,
    format('%s uploaded against %s.', p_amount, inv.total), o.id, '/finance/payments');
end $function$
;

-- used by run_simulation to act as each demo customer
CREATE OR REPLACE FUNCTION public._as(p_email text)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
begin
  perform set_config('request.jwt.claims', json_build_object('sub', (select id from profiles where email = p_email), 'role', 'authenticated')::text, true);
end $function$
;

create trigger order_items_snapshot before insert or update of product_id on order_items
  for each row execute function _snapshot_item();
