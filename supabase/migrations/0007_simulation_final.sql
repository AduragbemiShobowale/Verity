-- Final validation simulation for Chapter Four (test harness only; the application rules are untouched).
--
-- 500 orders per run: 15 planted error types x 20 orders, plus 200 clean orders, shuffled with a fixed seed.
-- Every order and account is created inside a block that is rolled back. The results, the answer key and the
-- inputs needed to replay the run are held in plpgsql variables and written to simulation_final_orders only
-- after the rollback, so nothing the validator reads during the run says which orders carry planted errors.
--
-- Replay mode (p_replay_run) resubmits the stored inputs of an earlier run, so that the unusual-quantity
-- sensitivity analysis scores exactly the same orders under a different factor or history length.

create table if not exists simulation_final_orders (
  run_id bigint not null references simulation_runs(id),
  replicate int, seed double precision, factor numeric, history int, replay_of bigint,
  seq int not null, order_no text, sim_day int,
  company text, contact text, email text, region text, address_label text,
  line_count int, units int, items jsonb,
  subtotal numeric, delivery_fee numeric, tax numeric, total numeric,
  planted_error text, rule_targeted boolean, expected_rule text, answer jsonb, input jsonb,
  outcome text, flagged boolean, status_after text, rules_triggered text[], messages text[],
  validation_ms numeric, events jsonb, harness_times jsonb,
  primary key (run_id, seq)
);
alter table simulation_final_orders enable row level security;
create policy sim_final_read on simulation_final_orders for select using (has_role('admin', 'ops'));

-- Used only inside the rolled-back simulation, so that status-history rows carry the wall-clock time of each
-- change instead of the transaction start time. It is never attached outside run_simulation_final.
create or replace function _sim_event_clock() returns trigger language plpgsql as $$
begin
  new.at := clock_timestamp();
  return new;
end $$;

create or replace function run_simulation_final(
  p_seed double precision, p_replicate int, p_factor numeric default null, p_history int default 4,
  p_replay_run bigint default null)
returns bigint language plpgsql security definer set search_path = public as $$
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
  types text[] := array['bad_sku','missing_address','missing_date','past_date','qty_below_min','qty_above_max',
                        'fractional_qty','over_stock','duplicate','inactive_product','inactive_customer','stale_price',
                        'wrong_product','qty_typo','wrong_address'];
  expected jsonb := '{"bad_sku":"sku","inactive_product":"sku","missing_address":"mandatory","missing_date":"mandatory",
    "past_date":"delivery","qty_below_min":"quantity","qty_above_max":"quantity","fractional_qty":"quantity",
    "over_stock":"stock","duplicate":"duplicate","inactive_customer":"customer_status","stale_price":"pricing"}';
  cats text[] := '{}';
  replay jsonb;
  emails text[] := '{}';
  c int; i int; k int; uid uuid; cid uuid; o uuid; r jsonb; pr record; p2 record; addr uuid;
  cat text; cust_email text; slug text; addr_label text; date_off int; items jsonb; unm jsonb; special jsonb; ans jsonb;
  inp jsonb; items_ids jsonb; excl text[]; v_sku text; v_sku2 text; q numeric; lo int; hi int;
  t_d0 timestamptz; t_d1 timestamptz; t0 timestamptz; t1 timestamptz; outcome text;
  last_clean jsonb := null;
  out_rows jsonb := '[]';
begin
  if not has_role('admin') then perform _err('Only an administrator can run the simulation.'); end if;
  if p_history < 3 or p_history > 20 then perform _err('History must be between 3 and 20 orders.'); end if;
  perform setseed(p_seed);

  if p_replay_run is not null then
    select jsonb_agg(jsonb_build_object('cat', planted_error, 'input', input, 'answer', answer) order by seq) into replay
      from simulation_final_orders where run_id = p_replay_run;
    if replay is null then perform _err('Nothing to replay for that run.'); end if;
    cats := array(select x->>'cat' from jsonb_array_elements(replay) x);
  else
    for i in 1..200 loop cats := cats || 'clean'::text; end loop;
    foreach cat in array types loop
      for i in 1..20 loop cats := cats || cat; end loop;
    end loop;
    cats := array(select x from unnest(cats) x order by random());
  end if;

  begin
    create trigger sim_event_clock before insert on order_events for each row execute function _sim_event_clock();
    update settings set value = 'false' where key = 'auto_approve_enabled';
    if p_factor is not null then update settings set value = to_jsonb(p_factor) where key = 'unusual_qty_factor'; end if;
    update products set active = false where sku = 'SAND-T';

    -- the same 20 fictional customers as run 4, each with p_history earlier orders
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
      addr := (select id from addresses where customer_id = cid and label = 'Head office');
      for k in 1..p_history loop
        o := save_draft(null, jsonb_build_object('address_id', addr, 'requested_date', current_date + 3, 'source', 'simulation',
               'items', jsonb_build_array(jsonb_build_object('product_id', (select id from products where sku = 'CEM-50'), 'qty', 20 + k),
                                          jsonb_build_object('product_id', (select id from products where sku = 'ROD-12'), 'qty', 10 + k))));
        perform submit_order(o, true);
      end loop;
    end loop;

    for i in 1..array_length(cats, 1) loop
      cat := cats[i];
      if replay is not null then
        inp := replay->(i - 1)->'input';
        ans := replay->(i - 1)->'answer';
      else
        -- generate one order carrying at most one planted error
        c := 1 + floor(random() * array_length(emails, 1))::int;
        cust_email := emails[c];
        addr_label := case when random() < 0.5 then 'Head office' else 'Site' end;
        date_off := 1 + floor(random() * 10)::int;
        unm := '[]'; special := null; ans := '{}'; excl := '{}'; items := '[]';

        if cat = 'wrong_product' then
          select a, b into v_sku, v_sku2 from (values ('ROD-12','ROD-16'), ('ROD-16','ROD-12'), ('PNT-20C','PNT-20W'),
            ('PNT-20W','PNT-20C'), ('PVC-2','PVC-4'), ('PVC-4','PVC-2')) v(a, b) order by random() limit 1;
          excl := array[v_sku, v_sku2];
        elsif cat = 'qty_typo' then
          v_sku := case when random() < 0.5 then 'CEM-50' else 'ROD-12' end;
          excl := array[v_sku];
        elsif cat in ('qty_below_min','qty_above_max','fractional_qty','over_stock') then
          select sku into v_sku from products where active and sku <> 'SAND-T' and min_qty > 1
            and (cat <> 'over_stock' or on_hand - reserved + 1 between min_qty and max_qty) order by random() limit 1;
          excl := array[v_sku];
        end if;

        -- clean base lines, drawn the same way as in run 4
        for pr in select * from products where active and on_hand - reserved >= min_qty * 3 and not (sku = any(excl))
                  order by random() limit 1 + floor(random() * 3)::int loop
          items := items || jsonb_build_array(jsonb_build_object('sku', pr.sku,
                     'qty', pr.min_qty + floor(random() * least(pr.max_qty - pr.min_qty, greatest((pr.on_hand - pr.reserved) / 4 - pr.min_qty, 1)))::int));
        end loop;

        if cat = 'bad_sku' then
          unm := jsonb_build_array(jsonb_build_object('row', jsonb_array_length(items) + 2, 'sku', 'XX-' || (100 + floor(random() * 900))::int, 'problem', 'not in the catalogue'));
          ans := jsonb_build_object('unknown_sku', unm->0->>'sku');
        elsif cat = 'missing_address' then ans := jsonb_build_object('intended_address', addr_label); addr_label := null;
        elsif cat = 'missing_date' then ans := jsonb_build_object('intended_date_offset', date_off); date_off := null;
        elsif cat = 'past_date' then ans := jsonb_build_object('intended_date_offset', date_off); date_off := -1 - floor(random() * 5)::int;
        elsif cat in ('qty_below_min','qty_above_max','fractional_qty','over_stock') then
          select * into p2 from products where sku = v_sku;
          q := case cat when 'qty_below_min' then p2.min_qty - 1
                        when 'qty_above_max' then p2.max_qty + 1 + floor(random() * 50)::int
                        when 'over_stock' then p2.on_hand - p2.reserved + 1
                        else p2.min_qty + 0.5 end;
          items := items || jsonb_build_array(jsonb_build_object('sku', v_sku, 'qty', q));
          ans := jsonb_build_object('sku', v_sku, 'entered_qty', q, 'min', p2.min_qty, 'max', p2.max_qty, 'available', p2.on_hand - p2.reserved);
        elsif cat = 'inactive_product' then
          items := items || jsonb_build_array(jsonb_build_object('sku', 'SAND-T', 'qty', 1));
          ans := jsonb_build_object('sku', 'SAND-T');
        elsif cat = 'duplicate' then
          if last_clean is not null then
            cust_email := last_clean->'input'->>'email'; addr_label := last_clean->'input'->>'address_label';
            date_off := (last_clean->'input'->>'date_offset')::int; items := last_clean->'input'->'items';
            ans := jsonb_build_object('duplicate_of', last_clean->>'order_no');
          else
            items := jsonb_build_array(jsonb_build_object('sku', 'CEM-50', 'qty', 20 + p_history), jsonb_build_object('sku', 'ROD-12', 'qty', 10 + p_history));
            addr_label := 'Head office';
            ans := jsonb_build_object('duplicate_of', 'history order ' || p_history);
          end if;
        elsif cat = 'inactive_customer' then
          special := jsonb_build_object('customer_status', case when random() < 0.5 then 'on_hold' else 'blocked' end);
          ans := special;
        elsif cat = 'stale_price' then
          v_sku := items->0->>'sku';
          special := jsonb_build_object('sku', v_sku, 'old_price', (select price from products where sku = v_sku),
                                        'new_price', round((select price from products where sku = v_sku) * 1.05, -2));
          ans := special;
        elsif cat = 'wrong_product' then
          select greatest(a.min_qty, b.min_qty), least(b.max_qty, b.on_hand - b.reserved, a.max_qty, greatest(a.min_qty, b.min_qty) + 19)
            into lo, hi from products a, products b where a.sku = v_sku and b.sku = v_sku2;
          q := lo + floor(random() * (hi - lo + 1))::int;
          items := items || jsonb_build_array(jsonb_build_object('sku', v_sku2, 'qty', q));
          ans := jsonb_build_object('intended_sku', v_sku, 'entered_sku', v_sku2, 'qty', q);
        elsif cat = 'qty_typo' then
          q := case v_sku when 'CEM-50' then 15 + floor(random() * 16)::int else 8 + floor(random() * 13)::int end;
          items := items || jsonb_build_array(jsonb_build_object('sku', v_sku, 'qty', q * 10));
          ans := jsonb_build_object('sku', v_sku, 'intended_qty', q, 'entered_qty', q * 10);
        elsif cat = 'wrong_address' then
          ans := jsonb_build_object('intended_address', addr_label);
          addr_label := case addr_label when 'Head office' then 'Site' else 'Head office' end;
          ans := ans || jsonb_build_object('entered_address', addr_label);
        end if;

        inp := jsonb_build_object('email', cust_email, 'address_label', addr_label, 'date_offset', date_off,
                                  'items', items, 'unmatched', unm, 'special', special);
      end if;

      -- submit through the same functions a customer uses
      cust_email := inp->>'email';
      perform _as(cust_email);
      cid := my_customer_id();
      addr := (select id from addresses where customer_id = cid and label = inp->>'address_label');
      select coalesce(jsonb_agg(jsonb_build_object('product_id', p.id, 'qty', x->'qty')), '[]') into items_ids
        from jsonb_array_elements(inp->'items') x join products p on p.sku = x->>'sku';
      t_d0 := clock_timestamp();
      o := save_draft(null, jsonb_build_object('address_id', addr,
             'requested_date', case when inp->>'date_offset' is null then null else current_date + (inp->>'date_offset')::int end,
             'source', 'simulation', 'items', items_ids, 'unmatched', inp->'unmatched'));
      t_d1 := clock_timestamp();
      if cat = 'inactive_customer' then
        update customers set status = (inp->'special'->>'customer_status')::customer_status where id = cid;
      elsif cat = 'stale_price' then
        update products set price = (inp->'special'->>'new_price')::numeric where sku = inp->'special'->>'sku';
      end if;
      t0 := clock_timestamp();
      r := submit_order(o, false);
      t1 := clock_timestamp();
      if cat = 'inactive_customer' then
        update customers set status = 'active' where id = cid;
      elsif cat = 'stale_price' then
        update products set price = (inp->'special'->>'old_price')::numeric where sku = inp->'special'->>'sku';
      end if;
      outcome := case when (r->>'needs_confirmation')::boolean then 'warn' else r->>'outcome' end;

      out_rows := out_rows || jsonb_build_array(jsonb_build_object(
        'seq', i, 'order_no', (select order_no from orders where id = o), 'sim_day', 1 + ((i - 1) * 10 / array_length(cats, 1)),
        'company', (select name from customers where id = cid), 'contact', (select contact_name from customers where id = cid),
        'email', cust_email, 'address_label', inp->>'address_label',
        'region', (select rg.name from orders oo join addresses a on a.id = oo.address_id join regions rg on rg.id = a.region_id where oo.id = o),
        'line_count', (select count(*) from order_items where order_id = o and qty_ordered > 0) + jsonb_array_length((select unmatched_lines from orders where id = o)),
        'units', coalesce((select sum(qty_ordered) from order_items where order_id = o and qty_ordered > 0), 0),
        'items', (select coalesce(jsonb_agg(jsonb_build_object('sku', product_sku, 'qty', qty_ordered, 'unit_price', unit_price) order by product_sku), '[]')
                  from order_items where order_id = o and qty_ordered > 0) || (select unmatched_lines from orders where id = o),
        'subtotal', (select subtotal from orders where id = o), 'delivery_fee', (select delivery_fee from orders where id = o),
        'tax', (select tax from orders where id = o), 'total', (select total from orders where id = o),
        'planted_error', cat, 'rule_targeted', expected ? cat, 'expected_rule', expected->>cat, 'answer', ans, 'input', inp,
        'outcome', outcome, 'status_after', coalesce(r->>'status', (select status::text from orders where id = o)),
        'rules', (select coalesce(jsonb_agg(distinct x->>'rule'), '[]') from jsonb_array_elements(r->'results') x where x->>'severity' <> 'pass'),
        'messages', (select coalesce(jsonb_agg(x->>'message'), '[]') from jsonb_array_elements(r->'results') x where x->>'severity' <> 'pass'),
        'ms', round(extract(epoch from t1 - t0) * 1000, 3),
        'events', (select jsonb_agg(jsonb_build_object('from', from_status, 'to', to_status, 'at', at, 'note', note) order by id) from order_events where order_id = o),
        'harness', jsonb_build_object('save_draft_start', t_d0, 'save_draft_end', t_d1, 'submit_start', t0, 'submit_end', t1)));

      if cat = 'clean' and coalesce(r->>'status', '') = 'pending_approval' then
        last_clean := jsonb_build_object('input', inp, 'order_no', (select order_no from orders where id = o));
      end if;
    end loop;
    raise exception 'SIM_ROLLBACK';
  exception when others then
    if sqlerrm <> 'SIM_ROLLBACK' then raise; end if;
  end;
  perform set_config('request.jwt.claims', claims, true);

  insert into simulation_runs (run_by, orders, summary)
  values (v_by, array_length(cats, 1), jsonb_build_object('kind', 'final', 'seed', p_seed, 'replicate', p_replicate,
          'factor', coalesce(p_factor, setting_num('unusual_qty_factor')), 'history', p_history, 'replay_of', p_replay_run,
          'customers', array_length(companies, 1)))
  returning id into v_run;

  insert into simulation_final_orders
  select v_run, p_replicate, p_seed, coalesce(p_factor, setting_num('unusual_qty_factor')), p_history, p_replay_run,
         (e->>'seq')::int, e->>'order_no', (e->>'sim_day')::int, e->>'company', e->>'contact', e->>'email', e->>'region', e->>'address_label',
         (e->>'line_count')::int, (e->>'units')::int, e->'items',
         (e->>'subtotal')::numeric, (e->>'delivery_fee')::numeric, (e->>'tax')::numeric, (e->>'total')::numeric,
         e->>'planted_error', (e->>'rule_targeted')::boolean, e->>'expected_rule', e->'answer', e->'input',
         e->>'outcome', e->>'outcome' in ('fail', 'warn'), e->>'status_after',
         array(select jsonb_array_elements_text(e->'rules')), array(select jsonb_array_elements_text(e->'messages')),
         (e->>'ms')::numeric, e->'events', e->'harness'
  from jsonb_array_elements(out_rows) e;
  return v_run;
end $$;
revoke all on function run_simulation_final(double precision, int, numeric, int, bigint) from public, anon;
