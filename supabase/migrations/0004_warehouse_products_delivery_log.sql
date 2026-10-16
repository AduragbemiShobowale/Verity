-- Warehouse can add new products; they stay hidden until Admin prices them.
-- Dispatch gets a delivery log showing how each delivery was confirmed.

alter table products add constraint products_active_needs_price check (not active or price > 0);
alter table products add column created_by uuid references profiles(id);

create or replace function warehouse_add_product(p_sku text, p_name text, p_unit text, p_qty int,
                                                 p_reference text, p_reorder_level int default 0)
returns uuid language plpgsql security definer set search_path = public as $$
declare v_id uuid; v_sku text := upper(trim(coalesce(p_sku, '')));
begin
  perform _require('warehouse');
  if v_sku = '' or trim(coalesce(p_name, '')) = '' then perform _err('SKU and name are required.'); end if;
  if v_sku !~ '^[A-Z0-9][A-Z0-9-]{1,30}$' then perform _err('Use letters, numbers and dashes for the SKU (e.g. PVC-6).'); end if;
  if exists (select 1 from products where sku = v_sku) then perform _err('A product with this SKU already exists. Use Stock in instead.'); end if;
  if coalesce(p_qty, 0) < 0 then perform _err('Quantity cannot be negative.'); end if;
  if coalesce(p_qty, 0) > 0 and trim(coalesce(p_reference, '')) = '' then perform _err('Enter the delivery note or PO reference for the stock.'); end if;

  insert into products (sku, name, unit, price, active, on_hand, reorder_level, created_by)
  values (v_sku, trim(p_name), coalesce(nullif(trim(p_unit), ''), 'unit'), 0, false, coalesce(p_qty, 0),
          greatest(coalesce(p_reorder_level, 0), 0), auth.uid())
  returning id into v_id;
  if coalesce(p_qty, 0) > 0 then
    insert into stock_movements (product_id, type, qty, reason, reference, user_id)
    values (v_id, 'in', p_qty, 'Opening stock for new product', trim(p_reference), auth.uid());
  end if;
  perform _notify_role('admin', 'product_needs_price', 'New product to price: ' || v_sku,
    trim(p_name) || ' was added by the warehouse. Set its price and limits, then activate it.', null, '/admin/catalogue');
  return v_id;
end $$;

-- One row per finished delivery attempt: who, when, and how it was confirmed.
create or replace function delivery_log(p_from date default null, p_to date default null)
returns table (delivery_id uuid, order_id uuid, order_no text, customer text, region text, driver text, vehicle text,
               assigned_at timestamptz, picked_up_at timestamptz, finished_at timestamptz, outcome text,
               confirmed_by text, wrong_code_attempts int, note text)
language sql stable security definer set search_path = public as $$
  select d.id, o.id, o.order_no, c.name, r.name, pr.full_name, v.plate,
         d.assigned_at, d.picked_up_at, coalesce(d.delivered_at, f.at), d.outcome,
         case d.outcome when 'delivered' then 'Customer code'
                        when 'override' then 'Ops Desk override'
                        when 'failed' then '—' else '—' end,
         case when d.outcome in ('delivered', 'override') then coalesce(dc.failed_attempts, 0) end,
         case d.outcome when 'override' then (select e.note from order_events e where e.order_id = o.id and e.to_status = 'delivered' order by e.id desc limit 1)
                        when 'failed' then d.failure_reason end
  from deliveries d
  join orders o on o.id = d.order_id
  join customers c on c.id = o.customer_id
  left join addresses a on a.id = o.address_id
  left join regions r on r.id = a.region_id
  left join profiles pr on pr.id = d.driver_id
  left join vehicles v on v.id = d.vehicle_id
  left join delivery_codes dc on dc.order_id = o.id
  left join lateral (select e.at from order_events e where e.order_id = o.id and e.to_status = 'delivery_failed'
                     and e.at >= d.assigned_at order by e.id limit 1) f on true
  where d.outcome in ('delivered', 'override', 'failed')
    and has_role('dispatch', 'ops', 'admin')
    and (p_from is null or coalesce(d.delivered_at, f.at, d.assigned_at)::date >= p_from)
    and (p_to is null or coalesce(d.delivered_at, f.at, d.assigned_at)::date <= p_to)
  order by coalesce(d.delivered_at, f.at, d.assigned_at) desc
$$;

-- printable invoice for the customer who owns it, Finance, Ops and Admin
create or replace function invoice_document(p_invoice uuid) returns jsonb
language plpgsql stable security definer set search_path = public as $$
declare inv invoices; v jsonb;
begin
  select * into inv from invoices where id = p_invoice;
  if inv.id is null or not (inv.customer_id = my_customer_id() or has_role('finance', 'ops', 'admin')) then
    perform _err('Invoice not found.');
  end if;
  select jsonb_build_object(
    'invoice', to_jsonb(inv),
    'order', (select jsonb_build_object('order_no', o.order_no, 'status', o.status, 'requested_date', o.requested_date,
              'address', a.label || ', ' || a.line, 'region', r.name)
              from orders o left join addresses a on a.id = o.address_id left join regions r on r.id = a.region_id where o.id = inv.order_id),
    'customer', (select jsonb_build_object('name', name, 'reg_no', reg_no, 'contact', contact_name, 'email', email, 'phone', phone, 'address', address)
                 from customers where id = inv.customer_id),
    'lines', (select coalesce(jsonb_agg(jsonb_build_object('sku', product_sku, 'name', product_name, 'unit', unit,
                'qty', qty_ordered, 'unit_price', unit_price, 'total', qty_ordered * unit_price) order by product_name), '[]')
              from order_items where order_id = inv.order_id and qty_ordered > 0),
    'payments', (select coalesce(jsonb_agg(jsonb_build_object('attempt', attempt_no, 'amount', amount, 'reference', reference,
                   'status', status, 'at', created_at) order by attempt_no), '[]') from payments where invoice_id = inv.id),
    'refunds', (select coalesce(jsonb_agg(jsonb_build_object('amount', amount, 'status', status, 'credit_note', credit_note_no,
                  'reason', reason) order by requested_at), '[]') from refunds where order_id = inv.order_id),
    'bank', setting('bank_details'),
    'tax_rate', setting_num('tax_rate')
  ) into v;
  return v;
end $$;

revoke execute on function warehouse_add_product(text, text, text, int, text, int), delivery_log(date, date), invoice_document(uuid) from public, anon;
grant execute on function warehouse_add_product(text, text, text, int, text, int), delivery_log(date, date), invoice_document(uuid) to authenticated;
