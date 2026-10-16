-- Pushes a demo order through approval, payment, picking and dispatch so the
-- driver handover can be tried by hand. p_stop_at: assigned | out_for_delivery | delivered.
-- Run from the SQL editor (needs _as from 0002 and the seed accounts):
--   select _stage_order('buyer@adebayo.example',
--     jsonb_build_array(jsonb_build_object('product_id', (select id from products where sku='TIL-6060'), 'qty', 25)),
--     'driver1@verity.example', 'assigned');
create or replace function _stage_order(p_customer text, p_items jsonb, p_driver text, p_stop_at text) returns text
language plpgsql security definer set search_path = public as $$
declare o uuid; inv uuid; r jsonb; addr uuid; v_no text;
begin
  perform _as(p_customer);
  addr := (select id from addresses where customer_id = my_customer_id() and active order by label limit 1);
  o := save_draft(null, jsonb_build_object('address_id', addr, 'requested_date', current_date + 1, 'items', p_items));
  r := submit_order(o, true);
  if r->>'status' = 'pending_approval' then perform _as('ops@verity.example'); perform approve_order(o, 'Demo'); end if;
  perform _as(p_customer);
  inv := (select id from invoices where order_id = o);
  perform upload_payment(inv, (select total from invoices where id = inv), 'DEMO-TRF-' || substr(o::text, 1, 6), null);
  perform _as('finance@verity.example');
  perform confirm_payment((select id from payments where invoice_id = inv));
  perform _as('warehouse@verity.example');
  perform start_picking(o);
  perform record_pick(o, (select jsonb_agg(jsonb_build_object('item_id', id, 'qty_found', qty_ordered)) from order_items where order_id = o and qty_ordered > 0));
  perform _as('dispatch@verity.example');
  perform assign_delivery(array[o], (select id from profiles where email = p_driver), (select min(id) from vehicles where active));
  if p_stop_at in ('out_for_delivery', 'delivered') then
    perform _as(p_driver); perform confirm_pickup(o);
  end if;
  if p_stop_at = 'delivered' then
    perform confirm_delivery(o, '000000');  -- one wrong attempt, so the log shows it
    perform confirm_delivery(o, (select code from delivery_code_reveals where order_id = o));
  end if;
  select order_no into v_no from orders where id = o;
  return v_no || ' -> ' || (select status from orders where id = o);
end $$;
revoke execute on function _stage_order(text, jsonb, text, text) from public, anon, authenticated;
