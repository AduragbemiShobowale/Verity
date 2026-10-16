-- Verity: core schema
-- Every table has RLS enabled. Reads are scoped by policy; state changes
-- go through SECURITY DEFINER functions (0002) so the order state machine,
-- stock and money rules are enforced on the server.

create extension if not exists pgcrypto with schema extensions;
create extension if not exists pg_cron;

-- ---------------------------------------------------------------- enums
create type app_role as enum ('customer','ops','finance','warehouse','dispatch','driver','admin');
create type user_status as enum ('active','inactive');
create type customer_status as enum ('awaiting_review','more_info','rejected','active','on_hold','blocked');
create type order_status as enum (
  'draft','submitted','validation_failed','pending_approval','rejected',
  'awaiting_payment','payment_verification','payment_rejected','paid',
  'picking','shortage_hold','packed','assigned','out_for_delivery',
  'delivery_failed','delivered','cancelled'
);
create type severity as enum ('pass','warn','fail');
create type invoice_status as enum ('issued','paid','expired','credited','cancelled');
create type payment_status as enum ('pending','confirmed','rejected');
create type refund_status as enum ('requested','paid');
create type shortage_choice as enum ('deliver_available','wait_restock','cancel_order');

-- ---------------------------------------------------------------- people
create table profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email text not null,
  full_name text,
  phone text,
  role app_role not null default 'customer',
  status user_status not null default 'active',
  must_change_password boolean not null default false,
  last_login timestamptz,
  created_at timestamptz not null default now()
);

create table regions (
  id serial primary key,
  name text not null unique,
  delivery_fee numeric(12,2) not null default 0 check (delivery_fee >= 0),
  active boolean not null default true
);

create table customers (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  reg_no text not null,
  contact_name text not null,
  email text not null,
  phone text not null,
  address text not null,
  industry text,
  expected_volume int,
  status customer_status not null default 'awaiting_review',
  payment_terms text not null default 'prepaid',
  credit_limit numeric(12,2) not null default 0,
  allowed_region_ids int[] not null default '{}',
  trusted boolean not null default false,
  admin_note text,
  rejection_reason text,
  reapply_after date,
  created_at timestamptz not null default now()
);
create unique index customers_reg_no_uq on customers (lower(reg_no));

create table customer_users (
  user_id uuid primary key references profiles(id) on delete cascade,
  customer_id uuid not null references customers(id) on delete cascade
);

create table registration_applications (
  id uuid primary key default gen_random_uuid(),
  customer_id uuid not null references customers(id) on delete cascade,
  rule_results jsonb not null default '[]',
  documents text[] not null default '{}',
  outcome text not null,                -- auto_approved | manual_review | auto_rejected | resubmitted
  decision text,                        -- accept | reject | hold | more_info
  decided_by uuid references profiles(id),
  decided_at timestamptz,
  note text,
  created_at timestamptz not null default now()
);

create table screening_list (
  id serial primary key,
  kind text not null check (kind in ('blocked_reg_no','blocked_email','blocked_domain','free_domain','preapproved_reg_no')),
  value text not null,
  note text,
  unique (kind, value)
);

create table addresses (
  id uuid primary key default gen_random_uuid(),
  customer_id uuid not null references customers(id) on delete cascade,
  label text not null,
  line text not null,
  region_id int not null references regions(id),
  instructions text,
  active boolean not null default true
);

-- ---------------------------------------------------------------- catalogue and stock
create table products (
  id uuid primary key default gen_random_uuid(),
  sku text not null unique,
  name text not null,
  unit text not null default 'unit',
  price numeric(12,2) not null check (price >= 0),
  active boolean not null default true,
  on_hand int not null default 0 check (on_hand >= 0),
  reserved int not null default 0 check (reserved >= 0),
  reorder_level int not null default 0,
  min_qty int not null default 1,
  max_qty int not null default 10000,
  created_at timestamptz not null default now()
);

create table stock_movements (
  id bigserial primary key,
  product_id uuid not null references products(id),
  type text not null check (type in ('in','reserve','release','pick','adjust')),
  qty int not null,
  reason text,
  reference text,
  order_id uuid,
  user_id uuid references profiles(id),
  at timestamptz not null default now()
);

-- ---------------------------------------------------------------- orders
create sequence order_no_seq start 1001;
create sequence invoice_no_seq start 5001;
create sequence credit_note_seq start 9001;

create table orders (
  id uuid primary key default gen_random_uuid(),
  order_no text not null unique default ('ORD-' || nextval('order_no_seq')),
  customer_id uuid not null references customers(id),
  status order_status not null default 'draft',
  source text not null default 'portal' check (source in ('portal','upload','reorder','simulation')),
  address_id uuid references addresses(id),
  requested_date date,
  notes text,
  subtotal numeric(12,2) not null default 0,
  delivery_fee numeric(12,2) not null default 0,
  tax numeric(12,2) not null default 0,
  total numeric(12,2) not null default 0,
  validation_outcome severity,
  unmatched_lines jsonb not null default '[]',
  duplicate_confirmed boolean not null default false,
  shortage_choice shortage_choice,
  shortage_at timestamptz,
  payment_attempts_allowed int not null default 3,
  cancel_requested_reason text,
  cancel_reason text,
  created_by uuid references profiles(id),
  submitted_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index orders_customer_idx on orders (customer_id);
create index orders_status_idx on orders (status);

create table order_items (
  id uuid primary key default gen_random_uuid(),
  order_id uuid not null references orders(id) on delete cascade,
  product_id uuid not null references products(id),
  qty_ordered int not null,
  qty_reserved int not null default 0,
  qty_picked int not null default 0,
  unit_price numeric(12,2) not null,
  product_sku text,      -- snapshot at save time, so customers and drivers
  product_name text,     -- can read lines without access to products
  unit text,
  unique (order_id, product_id)
);

-- the allowed moves of the state machine, in one place
create table order_transitions (
  from_status order_status not null,
  to_status order_status not null,
  primary key (from_status, to_status)
);
insert into order_transitions values
  ('draft','submitted'),
  ('validation_failed','submitted'),
  ('rejected','submitted'),
  ('submitted','validation_failed'),
  ('submitted','pending_approval'),
  ('submitted','awaiting_payment'),          -- auto-approval
  ('pending_approval','awaiting_payment'),
  ('pending_approval','rejected'),
  ('awaiting_payment','payment_verification'),
  ('payment_rejected','payment_verification'),
  ('payment_verification','paid'),
  ('payment_verification','payment_rejected'),
  ('paid','picking'),
  ('picking','packed'),
  ('picking','shortage_hold'),
  ('shortage_hold','picking'),
  ('shortage_hold','packed'),
  ('packed','assigned'),
  ('assigned','packed'),                     -- unassign / driver unavailable
  ('assigned','out_for_delivery'),
  ('out_for_delivery','delivered'),
  ('out_for_delivery','delivery_failed'),
  ('delivery_failed','assigned'),
  ('delivery_failed','packed'),
  -- cancellations
  ('draft','cancelled'),
  ('validation_failed','cancelled'),
  ('rejected','cancelled'),
  ('pending_approval','cancelled'),
  ('awaiting_payment','cancelled'),
  ('payment_rejected','cancelled'),
  ('payment_verification','cancelled'),
  ('paid','cancelled'),
  ('picking','cancelled'),
  ('shortage_hold','cancelled'),
  ('packed','cancelled'),
  ('assigned','cancelled');

create table order_events (
  id bigserial primary key,
  order_id uuid not null references orders(id) on delete cascade,
  from_status order_status,
  to_status order_status not null,
  note text,
  user_id uuid references profiles(id),
  at timestamptz not null default now()
);
create index order_events_order_idx on order_events (order_id, at);

create table validation_results (
  id bigserial primary key,
  order_id uuid not null references orders(id) on delete cascade,
  rule text not null,
  severity severity not null,
  field text,
  message text not null,
  current boolean not null default true,   -- false once a newer run replaces it
  run_at timestamptz not null default now()
);
create index validation_results_order_idx on validation_results (order_id);
create index validation_results_current_idx on validation_results (order_id) where current;

create table approvals (
  id bigserial primary key,
  order_id uuid not null references orders(id) on delete cascade,
  approver_id uuid references profiles(id),   -- null = auto-approved by rule
  decision text not null check (decision in ('approved','rejected')),
  comment text,
  decided_at timestamptz not null default now()
);

-- ---------------------------------------------------------------- money
create table invoices (
  id uuid primary key default gen_random_uuid(),
  invoice_no text not null unique default ('INV-' || nextval('invoice_no_seq')),
  order_id uuid not null unique references orders(id) on delete cascade,
  customer_id uuid not null references customers(id),
  subtotal numeric(12,2) not null,
  delivery_fee numeric(12,2) not null,
  tax numeric(12,2) not null,
  total numeric(12,2) not null,
  due_at timestamptz not null,
  status invoice_status not null default 'issued',
  created_at timestamptz not null default now()
);

create table payments (
  id uuid primary key default gen_random_uuid(),
  invoice_id uuid not null references invoices(id) on delete cascade,
  customer_id uuid not null references customers(id),
  amount numeric(12,2) not null check (amount > 0),
  method text not null default 'bank_transfer',
  reference text not null,
  proof_path text,
  attempt_no int not null,
  status payment_status not null default 'pending',
  uploaded_by uuid references profiles(id),
  verified_by uuid references profiles(id),
  verified_at timestamptz,
  reason text,
  created_at timestamptz not null default now()
);

create table refunds (
  id uuid primary key default gen_random_uuid(),
  order_id uuid not null references orders(id) on delete cascade,
  customer_id uuid not null references customers(id),
  amount numeric(12,2) not null check (amount > 0),
  reason text not null,
  status refund_status not null default 'requested',
  requested_by uuid references profiles(id),     -- null = raised by rule
  requested_at timestamptz not null default now(),
  reference text,
  paid_by uuid references profiles(id),
  paid_at timestamptz,
  credit_note_no text
);

-- ---------------------------------------------------------------- dispatch
create table vehicles (
  id serial primary key,
  plate text not null unique,
  description text,
  capacity int,
  active boolean not null default true
);

create table drivers (
  user_id uuid primary key references profiles(id) on delete cascade,
  phone text,
  licence_no text,
  active boolean not null default true
);

create table deliveries (
  id uuid primary key default gen_random_uuid(),
  order_id uuid not null references orders(id) on delete cascade,
  driver_id uuid not null references profiles(id),
  vehicle_id int references vehicles(id),
  assigned_by uuid references profiles(id),
  assigned_at timestamptz not null default now(),
  picked_up_at timestamptz,
  delivered_at timestamptz,
  outcome text check (outcome in ('delivered','failed','reassigned','override')),
  failure_reason text,
  current boolean not null default true
);
create index deliveries_driver_idx on deliveries (driver_id) where current;

-- the hash is used to check the code; the plain code is kept in a separate
-- table that only the order's own customer can read, and only once the
-- order is out for delivery
create table delivery_codes (
  order_id uuid primary key references orders(id) on delete cascade,
  code_hash text not null,
  issued_at timestamptz not null default now(),
  expires_at timestamptz not null,
  failed_attempts int not null default 0,
  locked boolean not null default false,
  used_at timestamptz
);
create table delivery_code_reveals (
  order_id uuid primary key references orders(id) on delete cascade,
  customer_id uuid not null references customers(id),
  code text not null
);

-- ---------------------------------------------------------------- platform
create table notifications (
  id bigserial primary key,
  user_id uuid not null references profiles(id) on delete cascade,
  event text not null,
  title text not null,
  body text,
  order_id uuid references orders(id) on delete cascade,
  link text,
  send_email boolean not null default false,
  email_sent_at timestamptz,
  read_at timestamptz,
  created_at timestamptz not null default now()
);
create index notifications_user_idx on notifications (user_id, created_at desc);

create table settings (
  key text primary key,
  value jsonb not null,
  description text
);
insert into settings (key, value, description) values
  ('tax_rate', '7.5', 'Tax percentage applied to subtotal plus delivery fee'),
  ('payment_window_hours', '48', 'Hours after approval to pay before automatic cancellation'),
  ('payment_reupload_grace_hours', '24', 'Minimum hours a customer has to re-upload after a rejected proof'),
  ('max_payment_attempts', '3', 'Proof uploads allowed before the Ops Desk steps in'),
  ('duplicate_window_hours', '24', 'Same items from the same customer within this window raise a duplicate warning'),
  ('price_tolerance', '0.01', 'Allowed difference between line price and price list'),
  ('unusual_qty_factor', '3', 'Warn when a quantity is this many times the customer average'),
  ('auto_approve_enabled', 'true', 'Auto-approve prepaid orders that pass every rule with no warnings'),
  ('auto_approve_max_total', '500000', 'Auto-approval only below this invoice total'),
  ('low_stock_warn_qty', '10', 'Customers see "Low stock" at or below this available quantity'),
  ('delivery_code_max_attempts', '5', 'Wrong code entries before the code locks'),
  ('delivery_code_valid_days', '7', 'Days a delivery code stays valid'),
  ('restock_wait_days', '7', 'Days an order may wait for restock before the Ops Desk is alerted'),
  ('stuck_order_hours', '24', 'Orders in one internal status longer than this are flagged as stuck'),
  ('bank_details', '{"bank":"Demo Bank Plc","account_name":"Verity Logistics Ltd","account_no":"0123456789"}', 'Shown on every invoice'),
  ('manual_review_volume', '1000', 'Registrations expecting more orders per month than this always go to manual review'),
  ('reapply_wait_days', '30', 'Days a rejected applicant must wait before reapplying'),
  ('require_documents', 'true', 'Registrations must include at least one document'),
  ('reject_free_domains', 'false', 'Auto-reject registrations from free e-mail domains (otherwise flag for review)'),
  ('default_payment_terms', '"prepaid"', 'Payment terms given to newly accepted customers'),
  ('default_credit_limit', '0', 'Credit limit given to newly accepted customers');

create table simulation_runs (
  id bigserial primary key,
  run_at timestamptz not null default now(),
  run_by uuid references profiles(id),
  orders int not null,
  summary jsonb not null
);

create table audit_log (
  id bigserial primary key,
  entity text not null,
  entity_id text,
  action text not null,
  old_value jsonb,
  new_value jsonb,
  user_id uuid,
  at timestamptz not null default now()
);
create index audit_log_at_idx on audit_log (at desc);

-- ---------------------------------------------------------------- helpers
create or replace function my_role() returns app_role
language sql stable security definer set search_path = public as $$
  select role from profiles where id = auth.uid() and status = 'active'
$$;

create or replace function has_role(variadic roles app_role[]) returns boolean
language sql stable security definer set search_path = public as $$
  select coalesce((select role = any(roles) from profiles where id = auth.uid() and status = 'active'), false)
$$;

create or replace function my_customer_id() returns uuid
language sql stable security definer set search_path = public as $$
  select customer_id from customer_users where user_id = auth.uid()
$$;

create or replace function is_my_order(p_order uuid) returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from orders where id = p_order and customer_id = my_customer_id())
$$;

create or replace function is_my_delivery(p_order uuid) returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from deliveries where order_id = p_order and driver_id = auth.uid() and current)
$$;

create or replace function setting(k text) returns jsonb
language sql stable security definer set search_path = public as $$
  select value from settings where key = k
$$;

create or replace function setting_num(k text) returns numeric
language sql stable security definer set search_path = public as $$
  select (value #>> '{}')::numeric from settings where key = k
$$;

create or replace function audit(p_entity text, p_entity_id text, p_action text, p_old jsonb, p_new jsonb)
returns void language sql security definer set search_path = public as $$
  insert into audit_log (entity, entity_id, action, old_value, new_value, user_id)
  values (p_entity, p_entity_id, p_action, p_old, p_new, auth.uid())
$$;

-- generic audit trigger for admin-maintained tables
create or replace function audit_trigger() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  insert into audit_log (entity, entity_id, action, old_value, new_value, user_id)
  values (tg_table_name,
          coalesce((case when tg_op = 'DELETE' then to_jsonb(old) else to_jsonb(new) end)->>'id',
                   (case when tg_op = 'DELETE' then to_jsonb(old) else to_jsonb(new) end)->>'key'),
          lower(tg_op),
          case when tg_op in ('UPDATE','DELETE') then to_jsonb(old) end,
          case when tg_op in ('INSERT','UPDATE') then to_jsonb(new) end,
          auth.uid());
  return coalesce(new, old);
end $$;

create trigger audit_products after insert or update or delete on products for each row execute function audit_trigger();
create trigger audit_regions after insert or update or delete on regions for each row execute function audit_trigger();
create trigger audit_settings after insert or update or delete on settings for each row execute function audit_trigger();
create trigger audit_screening after insert or update or delete on screening_list for each row execute function audit_trigger();
create trigger audit_vehicles after insert or update or delete on vehicles for each row execute function audit_trigger();
create trigger audit_profiles after update on profiles for each row
  when (old.role is distinct from new.role or old.status is distinct from new.status)
  execute function audit_trigger();

-- new auth user -> profile (customers self-register; staff are created by the admin function)
create or replace function handle_new_user() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  insert into profiles (id, email, full_name, role, must_change_password)
  values (new.id, new.email,
          coalesce(new.raw_user_meta_data->>'full_name', ''),
          'customer',
          false)
  on conflict (id) do nothing;
  return new;
end $$;
create trigger on_auth_user_created after insert on auth.users
  for each row execute function handle_new_user();

-- ---------------------------------------------------------------- RLS
alter table profiles enable row level security;
alter table regions enable row level security;
alter table customers enable row level security;
alter table customer_users enable row level security;
alter table registration_applications enable row level security;
alter table screening_list enable row level security;
alter table addresses enable row level security;
alter table products enable row level security;
alter table stock_movements enable row level security;
alter table orders enable row level security;
alter table order_items enable row level security;
alter table order_transitions enable row level security;
alter table order_events enable row level security;
alter table validation_results enable row level security;
alter table approvals enable row level security;
alter table invoices enable row level security;
alter table payments enable row level security;
alter table refunds enable row level security;
alter table vehicles enable row level security;
alter table drivers enable row level security;
alter table deliveries enable row level security;
alter table delivery_codes enable row level security;
alter table delivery_code_reveals enable row level security;
alter table notifications enable row level security;
alter table settings enable row level security;
alter table audit_log enable row level security;
alter table simulation_runs enable row level security;

-- profiles
create policy profiles_self on profiles for select using (id = auth.uid());
create policy profiles_staff on profiles for select using (has_role('admin','ops','dispatch','finance','warehouse'));
create policy profiles_admin_update on profiles for update using (has_role('admin')) with check (has_role('admin'));

-- reference data
create policy regions_read on regions for select using (auth.uid() is not null);
create policy regions_admin on regions for all using (has_role('admin')) with check (has_role('admin'));
create policy transitions_read on order_transitions for select using (auth.uid() is not null);
create policy settings_read on settings for select using (auth.uid() is not null);
create policy settings_admin on settings for update using (has_role('admin')) with check (has_role('admin'));
create policy screening_admin on screening_list for all using (has_role('admin')) with check (has_role('admin'));

-- customers
create policy customers_own on customers for select using (id = my_customer_id());
create policy customers_staff on customers for select using (has_role('admin','ops','finance','dispatch','warehouse'));
create policy customer_users_own on customer_users for select using (user_id = auth.uid() or has_role('admin','ops'));
create policy reg_apps_own on registration_applications for select using (customer_id = my_customer_id());
create policy reg_apps_admin on registration_applications for select using (has_role('admin'));
create policy addresses_own on addresses for select using (customer_id = my_customer_id());
create policy addresses_staff on addresses for select using (has_role('admin','ops','dispatch','warehouse'));

-- products: staff read full rows; customers read through catalogue view (no raw counts)
create policy products_staff on products for select using (has_role('admin','ops','finance','warehouse'));
create policy products_admin on products for all using (has_role('admin')) with check (has_role('admin'));
create policy stock_movements_staff on stock_movements for select using (has_role('admin','ops','warehouse'));

-- orders and children
create policy orders_own on orders for select using (customer_id = my_customer_id());
create policy orders_staff on orders for select using (has_role('admin','ops','finance','warehouse','dispatch'));
-- drivers read their deliveries only through driver_deliveries(), which has no prices
create policy orders_driver on orders for select using (false);

create policy items_own on order_items for select using (is_my_order(order_id));
create policy items_staff on order_items for select using (has_role('admin','ops','finance','warehouse','dispatch'));
create policy items_driver on order_items for select using (false);

create policy events_own on order_events for select using (is_my_order(order_id));
create policy events_staff on order_events for select using (has_role('admin','ops','finance','warehouse','dispatch'));

create policy vr_own on validation_results for select using (is_my_order(order_id));
create policy vr_staff on validation_results for select using (has_role('admin','ops'));
create policy approvals_staff on approvals for select using (has_role('admin','ops'));

-- money (drivers have no policy at all)
create policy invoices_own on invoices for select using (customer_id = my_customer_id());
create policy invoices_staff on invoices for select using (has_role('admin','ops','finance'));
create policy payments_own on payments for select using (customer_id = my_customer_id());
create policy payments_staff on payments for select using (has_role('admin','ops','finance'));
create policy refunds_own on refunds for select using (customer_id = my_customer_id());
create policy refunds_staff on refunds for select using (has_role('admin','ops','finance'));

-- dispatch
create policy vehicles_read on vehicles for select using (has_role('admin','dispatch','driver'));
create policy vehicles_admin on vehicles for all using (has_role('admin','dispatch')) with check (has_role('admin','dispatch'));
create policy drivers_read on drivers for select using (has_role('admin','dispatch','ops') or user_id = auth.uid());
create policy deliveries_staff on deliveries for select using (has_role('admin','ops','dispatch'));
create policy deliveries_driver on deliveries for select using (driver_id = auth.uid());
create policy deliveries_own on deliveries for select using (is_my_order(order_id));

-- delivery codes: nobody reads the hash table from the client
create policy code_meta_staff on delivery_codes for select using (false);
create policy code_reveal_own on delivery_code_reveals for select using (
  customer_id = my_customer_id()
  and exists (select 1 from orders o where o.id = order_id and o.status = 'out_for_delivery'));

-- notifications
create policy notif_own on notifications for select using (user_id = auth.uid());
create policy notif_own_update on notifications for update using (user_id = auth.uid()) with check (user_id = auth.uid());

-- audit: admin read only, no write policy for anyone
create policy audit_admin on audit_log for select using (has_role('admin'));
create policy sim_read on simulation_runs for select using (has_role('admin','ops'));
