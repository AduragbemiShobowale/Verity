-- Detailed validation simulation for the dissertation's technical chapter.
-- Creates 20 fictional customer companies, pushes N orders through the real
-- save_draft / submit_order functions with known planted errors, records every
-- order's details and outcome in simulation_orders, then rolls back the orders
-- and customers so the live system is untouched.

create table simulation_orders (
  run_id bigint not null references simulation_runs(id) on delete cascade,
  seq int not null,
  sim_day int not null,                 -- simulated arrival day (1-10), for charts only
  company text not null,
  contact text not null,
  email text not null,
  phone text not null,
  region text,
  line_count int not null,
  units int not null,
  items jsonb not null,
  subtotal numeric(14,2),
  delivery_fee numeric(14,2),
  tax numeric(14,2),
  total numeric(14,2),
  planted_error text not null,          -- 'clean' or the error type planted
  rule_targeted boolean not null,       -- is there a validation rule for this error type?
  outcome text not null,                -- pass | warn | fail
  status_after text,
  rules_triggered text[] not null default '{}',
  messages text[] not null default '{}',
  validation_ms numeric(10,3) not null,
  primary key (run_id, seq)
);
alter table simulation_orders enable row level security;
create policy sim_orders_read on simulation_orders for select using (has_role('admin', 'ops'));
grant select on simulation_orders to authenticated;

create or replace function run_simulation_detailed(p_n int default 500, p_seed float default 0.42) returns bigint
language plpgsql security definer set search_path = public as $$
#variable_conflict use_column
declare
  v_by uuid := auth.uid();
  claims text := current_setting('request.jwt.claims', true);
  v_run bigint;
  companies text[][] := array[
    ['Adeyemi & Sons Construction Ltd','Folake Adeyemi','Ikeja'],
    ['Kanu Brothers Building Supplies','Chukwuemeka Kanu','Lagos Mainland'],
    ['Ibadan Prime Homes Ltd','Oluwaseun Afolabi','Ibadan'],
    ['Lekki Coastal Developers','Amina Bello','Lekki-Ajah'],
    ['Northgate Realty Abuja','Ibrahim Musa','Abuja'],
    ['Eko Bridge Contractors','Tolulope Ogunleye','Lagos Island'],
    ['Greenfield Estates Nigeria','Ngozi Eze','Lekki-Ajah'],
    ['Ola-Ade Hardware & Tiles','Babatunde Oladipo','Ikeja'],
    ['Zuma Rock Engineering','Hauwa Abdullahi','Abuja'],
    ['Oyo Central Builders','Adewale Akinyemi','Ibadan'],
    ['Marina Point Facilities','Kemi Lawson','Lagos Island'],
    ['Surulere Paint & Finish','Uche Nwosu','Lagos Mainland'],
    ['Agege Steel Works','Yusuf Adebanjo','Ikeja'],
    ['Ajah Sunrise Housing Co-op','Blessing Okoro','Lekki-Ajah'],
    ['Gwarinpa Homes Ltd','Fatima Sani','Abuja'],
    ['Bodija Interiors','Segun Olatunji','Ibadan'],
    ['Victoria Island Fit-Out Ltd','Chiamaka Obi','Lagos Island'],
    ['Yaba Tech Hub Builders','Emeka Okafor','Lagos Mainland'],
    ['Magodo Residential Ltd','Funmilayo Adeleke','Ikeja'],
    ['Apapa Port Works Supplies','Garba Usman','Lagos Mainland']];
  cats text[] := array['clean','clean','clean','clean','clean','clean','clean','clean','clean','clean',
                       'bad_sku','missing_address','missing_date','past_date','qty_below_min','qty_above_max',
                       'fractional_qty','over_stock','duplicate','inactive_product',
                       'wrong_product','qty_typo','wrong_address'];
  targeted text[] := array['bad_sku','missing_address','missing_date','past_date','qty_below_min','qty_above_max',
                           'fractional_qty','over_stock','duplicate','inactive_product'];
  emails text[] := '{}';
  c int; i int; uid uuid; cid uuid; o uuid; r jsonb; items jsonb; pr record; p2 record; addr uuid; addr2 uuid;
  v_date date; v_unm jsonb; outcome text; cat text; cust_email text; t0 timestamptz; ms numeric;
  last_items jsonb := null; last_items_cust text := null;
  rows jsonb := '[]'; slug text;
begin
  if not has_role('admin') then perform _err('Only an administrator can run the simulation.'); end if;
  if p_n < 10 or p_n > 2000 then perform _err('Choose between 10 and 2000 orders.'); end if;
  perform setseed(p_seed);

  begin
    update settings set value = 'false' where key = 'auto_approve_enabled';
    update products set active = false where sku = 'SAND-T';

    -- 20 fictional customers, each with two saved addresses and a short order history
    for c in 1..array_length(companies, 1) loop
      slug := lower(regexp_replace(split_part(companies[c][1], ' ', 1), '[^a-zA-Z]', '', 'g'));
      cust_email := lower(split_part(companies[c][2], ' ', 1)) || '.' || lower(split_part(companies[c][2], ' ', 2)) || '@' || slug || c || '.example';
      emails := emails || cust_email;
      uid := _seed_user(cust_email, companies[c][2], 'customer', 'Sim-' || md5(random()::text));
      insert into customers (name, reg_no, contact_name, email, phone, address, industry, expected_volume, status)
      values (companies[c][1], 'RC-SIM-' || lpad(c::text, 4, '0'), companies[c][2], cust_email,
              '080' || lpad((30000000 + c * 104729)::text, 8, '0'), 'Head office, ' || companies[c][3],
              'Construction', 20 + c, 'active') returning id into cid;
      insert into customer_users values (uid, cid);
      insert into addresses (customer_id, label, line, region_id) values
        (cid, 'Head office', (10 + c) || ' Main Road, ' || companies[c][3], (select id from regions where name = companies[c][3])),
        (cid, 'Site', 'Plot ' || (100 + c) || ', ' || companies[c][3], (select id from regions where name = companies[c][3]));
      perform _as(cust_email);
      addr := (select id from addresses where customer_id = cid order by label limit 1);
      for i in 1..4 loop
        o := save_draft(null, jsonb_build_object('address_id', addr, 'requested_date', current_date + 3, 'source', 'simulation',
               'items', jsonb_build_array(jsonb_build_object('product_id', (select id from products where sku='CEM-50'), 'qty', 20 + i),
                                          jsonb_build_object('product_id', (select id from products where sku='ROD-12'), 'qty', 10 + i))));
        perform submit_order(o, true);
      end loop;
    end loop;

    for i in 1..p_n loop
      cat := cats[1 + floor(random() * array_length(cats, 1))::int];
      c := 1 + floor(random() * array_length(emails, 1))::int;
      cust_email := emails[c];
      perform _as(cust_email);
      addr := (select id from addresses where customer_id = my_customer_id() order by random() limit 1);
      v_date := current_date + 1 + floor(random() * 10)::int;
      v_unm := '[]';
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
          cat := 'clean';
        end if;
      elsif cat = 'inactive_product' then
        items := items || jsonb_build_array(jsonb_build_object('product_id', (select id from products where sku='SAND-T'), 'qty', 1));
      elsif cat = 'duplicate' then
        if last_items is not null then
          cust_email := last_items_cust; perform _as(cust_email);
          items := last_items;
          addr := (select id from addresses where customer_id = my_customer_id() order by label limit 1);
        else cat := 'clean'; end if;
      elsif cat = 'wrong_product' then
        select * into p2 from products where sku = (array['ROD-16','ROD-12','PNT-20C','PNT-20W','PVC-2','PVC-4'])[1 + floor(random()*6)::int];
        items := jsonb_build_array(jsonb_build_object('product_id', p2.id, 'qty', least(p2.min_qty + floor(random() * 20)::int, greatest(p2.on_hand - p2.reserved, p2.min_qty))));
      elsif cat = 'qty_typo' then
        items := jsonb_build_array(jsonb_build_object('product_id', (select id from products where sku = 'CEM-50'), 'qty', 200 + floor(random()*20)::int));
      elsif cat = 'wrong_address' then
        addr := (select id from addresses where customer_id = my_customer_id() order by label desc limit 1);
      end if;

      o := save_draft(null, jsonb_build_object('address_id', addr, 'requested_date', v_date, 'source', 'simulation', 'items', items, 'unmatched', v_unm));
      t0 := clock_timestamp();
      r := submit_order(o, false);
      ms := extract(epoch from clock_timestamp() - t0) * 1000;
      outcome := case when (r->>'needs_confirmation')::boolean then 'warn' else r->>'outcome' end;

      rows := rows || jsonb_build_array(jsonb_build_object(
        'seq', i, 'sim_day', 1 + ((i - 1) * 10 / p_n),
        'company', (select name from customers where id = my_customer_id()),
        'contact', (select contact_name from customers where id = my_customer_id()),
        'email', cust_email,
        'phone', (select phone from customers where id = my_customer_id()),
        'region', (select rg.name from orders oo join addresses a on a.id = oo.address_id join regions rg on rg.id = a.region_id where oo.id = o),
        'line_count', (select count(*) from order_items where order_id = o and qty_ordered > 0) + jsonb_array_length(v_unm),
        'units', coalesce((select sum(qty_ordered) from order_items where order_id = o and qty_ordered > 0), 0),
        'items', (select coalesce(jsonb_agg(jsonb_build_object('sku', product_sku, 'qty', qty_ordered, 'unit_price', unit_price)), '[]')
                  from order_items where order_id = o and qty_ordered > 0) || v_unm,
        'subtotal', (select subtotal from orders where id = o), 'delivery_fee', (select delivery_fee from orders where id = o),
        'tax', (select tax from orders where id = o), 'total', (select total from orders where id = o),
        'planted_error', cat, 'rule_targeted', cat = any(targeted),
        'outcome', outcome, 'status_after', coalesce(r->>'status', (select status::text from orders where id = o)),
        'rules', (select coalesce(jsonb_agg(distinct x->>'rule'), '[]') from jsonb_array_elements(r->'results') x where x->>'severity' <> 'pass'),
        'messages', (select coalesce(jsonb_agg(x->>'message'), '[]') from jsonb_array_elements(r->'results') x where x->>'severity' <> 'pass'),
        'ms', round(ms, 3)));
      if cat = 'clean' and outcome = 'pass' then last_items := items; last_items_cust := cust_email; end if;
    end loop;
    raise exception 'SIM_ROLLBACK';
  exception when others then
    if sqlerrm <> 'SIM_ROLLBACK' then raise; end if;
  end;
  perform set_config('request.jwt.claims', claims, true);

  insert into simulation_runs (run_by, orders, summary)
  values (v_by, p_n, jsonb_build_object('kind', 'detailed', 'seed', p_seed, 'customers', array_length(companies, 1)))
  returning id into v_run;

  insert into simulation_orders (run_id, seq, sim_day, company, contact, email, phone, region, line_count, units, items,
    subtotal, delivery_fee, tax, total, planted_error, rule_targeted, outcome, status_after, rules_triggered, messages, validation_ms)
  select v_run, (e->>'seq')::int, (e->>'sim_day')::int, e->>'company', e->>'contact', e->>'email', e->>'phone', e->>'region',
         (e->>'line_count')::int, (e->>'units')::int, e->'items',
         (e->>'subtotal')::numeric, (e->>'delivery_fee')::numeric, (e->>'tax')::numeric, (e->>'total')::numeric,
         e->>'planted_error', (e->>'rule_targeted')::boolean, e->>'outcome', e->>'status_after',
         array(select jsonb_array_elements_text(e->'rules')), array(select jsonb_array_elements_text(e->'messages')),
         (e->>'ms')::numeric
  from jsonb_array_elements(rows) e;

  update simulation_runs set summary = summary || (
    select jsonb_build_object(
      'total', count(*),
      'clean', count(*) filter (where planted_error = 'clean'),
      'clean_passed', count(*) filter (where planted_error = 'clean' and outcome = 'pass'),
      'targeted', count(*) filter (where rule_targeted),
      'targeted_caught', count(*) filter (where rule_targeted and outcome <> 'pass'),
      'untargeted', count(*) filter (where planted_error <> 'clean' and not rule_targeted),
      'untargeted_caught', count(*) filter (where planted_error <> 'clean' and not rule_targeted and outcome <> 'pass'),
      'avg_validation_ms', round(avg(validation_ms), 2))
    from simulation_orders where run_id = v_run)
  where id = v_run;

  -- same shape as run_simulation, so the Reports page can show either
  update simulation_runs set summary = summary || jsonb_build_object(
    'by_category', (select jsonb_object_agg(planted_error, jsonb_build_object('n', n, 'flagged', f, 'blocked', b)) from (
        select planted_error, count(*) n, count(*) filter (where outcome <> 'pass') f, count(*) filter (where outcome = 'fail') b
        from simulation_orders where run_id = v_run group by 1) x),
    'accuracy_targeted', round(100.0 * ((summary->>'targeted_caught')::int + (summary->>'clean_passed')::int)
                               / nullif((summary->>'targeted')::int + (summary->>'clean')::int, 0), 1),
    'accuracy_all', round(100.0 * ((summary->>'targeted_caught')::int + (summary->>'untargeted_caught')::int + (summary->>'clean_passed')::int)
                          / nullif((summary->>'total')::int, 0), 1),
    'mandatory_complete', 100)
  where id = v_run;
  return v_run;
end $$;
revoke execute on function run_simulation_detailed(int, float) from public, anon;
grant execute on function run_simulation_detailed(int, float) to authenticated;
