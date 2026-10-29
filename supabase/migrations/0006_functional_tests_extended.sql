-- Extended functional tests for Chapter Four (cases 15 onwards). Test harness only:
-- every change is made inside a block that is rolled back, and the results are returned as jsonb.
-- p_upload is the output of src/lib/upload.js rowsToOrder() for the sample sheet
-- (docs/chapter4_final/02_functional_tests/sample_import_old_price.csv).
create or replace function _test_extended(p_upload jsonb)
returns jsonb language plpgsql security definer set search_path = public as $$
declare
  log jsonb := '[]'; r jsonb; o uuid; st text; err text;
  cust uuid := (select id from customers where email = 'buyer@adebayo.example');
  addr uuid;
  cem uuid := (select id from products where sku = 'CEM-50');
  rod uuid := (select id from products where sku = 'ROD-12');
  v_price numeric := (select price from products where sku = 'CEM-50');
  draft jsonb;
begin
  if cust is null then
    cust := (select cu.customer_id from customer_users cu join profiles p on p.id = cu.user_id where p.email = 'buyer@adebayo.example');
  end if;
  addr := (select id from addresses where customer_id = cust and active order by label limit 1);
  begin
    perform _as('buyer@adebayo.example');

    -- 15a to 15c: a customer who is not active cannot save or submit an order
    foreach st in array array['awaiting_review', 'on_hold', 'blocked'] loop
      update customers set status = st::customer_status where id = cust;
      begin
        o := save_draft(null, jsonb_build_object('address_id', addr, 'requested_date', current_date + 2,
               'items', jsonb_build_array(jsonb_build_object('product_id', cem, 'qty', 21))));
        log := log || jsonb_build_object('case', '15_' || st, 'customer_status', st, 'result', 'draft saved (not blocked)');
      exception when others then
        log := log || jsonb_build_object('case', '15_' || st, 'customer_status', st, 'result', 'blocked', 'error', sqlerrm);
      end;
    end loop;

    -- 15d: draft saved while active, account put on hold before submission
    update customers set status = 'active' where id = cust;
    o := save_draft(null, jsonb_build_object('address_id', addr, 'requested_date', current_date + 2,
           'items', jsonb_build_array(jsonb_build_object('product_id', cem, 'qty', 22))));
    update customers set status = 'on_hold' where id = cust;
    r := submit_order(o, false);
    log := log || jsonb_build_object('case', '15_on_hold_at_submit', 'status', r->>'status', 'outcome', r->>'outcome', 'results', r->'results');
    update customers set status = 'active' where id = cust;

    -- 16a: price changed by Admin between save_draft and submit_order
    o := save_draft(null, jsonb_build_object('address_id', addr, 'requested_date', current_date + 2,
           'items', jsonb_build_array(jsonb_build_object('product_id', cem, 'qty', 23))));
    draft := jsonb_build_object('unit_price_at_save', (select unit_price from order_items where order_id = o and product_id = cem));
    update products set price = v_price + 400 where id = cem;
    r := submit_order(o, false);
    log := log || jsonb_build_object('case', '16_price_changed_before_submit', 'list_price_before', v_price, 'list_price_after', v_price + 400)
               || draft || jsonb_build_object('status', r->>'status', 'outcome', r->>'outcome', 'results', r->'results');
    update products set price = v_price where id = cem;

    -- 16b and 18: uploaded sheet with an old unit price and one line that is not in the catalogue
    o := save_draft(null, jsonb_build_object('address_id', addr, 'requested_date', current_date + 2, 'source', 'upload',
           'items', p_upload->'items', 'unmatched', p_upload->'unmatched'));
    draft := jsonb_build_object('saved_lines', (select jsonb_agg(jsonb_build_object('sku', p.sku, 'qty', oi.qty_ordered, 'unit_price', oi.unit_price) order by p.sku)
                                               from order_items oi join products p on p.id = oi.product_id where oi.order_id = o and oi.qty_ordered > 0),
                                'unmatched_saved', (select unmatched_lines from orders where id = o));
    r := submit_order(o, false);
    log := log || jsonb_build_object('case', '16_18_upload_old_price_and_unmatched') || draft
               || jsonb_build_object('status', r->>'status', 'outcome', r->>'outcome', 'results', r->'results');

    -- 17a: automatic approval on
    update settings set value = 'true' where key = 'auto_approve_enabled';
    o := save_draft(null, jsonb_build_object('address_id', addr, 'requested_date', current_date + 2,
           'items', jsonb_build_array(jsonb_build_object('product_id', cem, 'qty', 24), jsonb_build_object('product_id', rod, 'qty', 11))));
    r := submit_order(o, false);
    log := log || jsonb_build_object('case', '17_auto_approve_on', 'status', r->>'status', 'outcome', r->>'outcome', 'auto_approved', r->>'auto_approved',
               'total', (select total from orders where id = o),
               'events', (select jsonb_agg(jsonb_build_object('to', to_status, 'note', note) order by id) from order_events where order_id = o));

    -- 17b: automatic approval off
    update settings set value = 'false' where key = 'auto_approve_enabled';
    o := save_draft(null, jsonb_build_object('address_id', addr, 'requested_date', current_date + 2,
           'items', jsonb_build_array(jsonb_build_object('product_id', cem, 'qty', 26), jsonb_build_object('product_id', rod, 'qty', 12))));
    r := submit_order(o, false);
    log := log || jsonb_build_object('case', '17_auto_approve_off', 'status', r->>'status', 'outcome', r->>'outcome', 'auto_approved', r->>'auto_approved',
               'total', (select total from orders where id = o),
               'events', (select jsonb_agg(jsonb_build_object('to', to_status, 'note', note) order by id) from order_events where order_id = o));

    raise exception 'ROLLBACK_TEST';
  exception when others then
    if sqlerrm <> 'ROLLBACK_TEST' then
      log := log || jsonb_build_object('case', 'ERROR', 'error', sqlerrm);
    end if;
  end;
  return log;
end $$;
revoke all on function _test_extended(jsonb) from public, anon, authenticated;
