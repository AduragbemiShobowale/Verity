-- Row-level security check run on 2026-10-27 09:35:53 UTC through the Supabase SQL interface.
-- For each account the session switches to the database role "authenticated" with that user's JWT claims,
-- exactly as the browser client does, and counts the rows each table returns. Totals in the database at the time:
-- customers 3, products 12, orders 3, invoices 3, payments 3, delivery_codes 0, audit_log 85, settings 21, simulation_orders 500.
-- Pattern repeated for each account (results in rls_results_2026-10-27.csv):
create temp table rls_out(email text, tbl text, n int, at timestamptz default clock_timestamp());
grant insert, select on rls_out to authenticated;
create temp table who(email text, claims text);
insert into who select e, _claims(e) from unnest(array['admin@verity.example','ops@verity.example','finance@verity.example',
  'warehouse@verity.example','dispatch@verity.example','driver1@verity.example','buyer@adebayo.example','orders@okafor.example']) e;
select set_config('request.jwt.claims', (select claims from who where email = 'buyer@adebayo.example'), true);
set local role authenticated;
insert into rls_out(email, tbl, n) select 'buyer@adebayo.example', t, c from (values
  ('customers', (select count(*) from customers)), ('products', (select count(*) from products)),
  ('orders', (select count(*) from orders)), ('invoices', (select count(*) from invoices)),
  ('payments', (select count(*) from payments)), ('delivery_codes', (select count(*) from delivery_codes)),
  ('audit_log', (select count(*) from audit_log)), ('settings', (select count(*) from settings)),
  ('simulation_orders', (select count(*) from simulation_orders))) v(t, c);
with u as (update products set price = 1 where sku = 'CEM-50' returning 1)
insert into rls_out(email, tbl, n) select 'buyer@adebayo.example', 'WRITE products.price', count(*) from u;
reset role;
-- ... same block for each other account ...
select json_agg(r order by r.at) from rls_out r;
