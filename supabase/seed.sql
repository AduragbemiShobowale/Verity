-- Verity demo data. Run once on a fresh project after the migrations.
-- Every demo account uses the password VerityDemo#2026 and an address on the
-- reserved .example domain, so no real inbox can ever receive mail from it.
-- Change or remove these accounts before real use.

CREATE OR REPLACE FUNCTION public._seed_user(p_email text, p_name text, p_role app_role, p_pw text)
 RETURNS uuid
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare v_id uuid := gen_random_uuid();
begin
  insert into auth.users (instance_id, id, aud, role, email, encrypted_password, email_confirmed_at,
    raw_app_meta_data, raw_user_meta_data, created_at, updated_at, confirmation_token, email_change, email_change_token_new, recovery_token)
  values ('00000000-0000-0000-0000-000000000000', v_id, 'authenticated', 'authenticated', p_email,
    extensions.crypt(p_pw, extensions.gen_salt('bf')), now(),
    '{"provider":"email","providers":["email"]}', jsonb_build_object('full_name', p_name), now(), now(), '', '', '', '');
  insert into auth.identities (id, user_id, provider_id, identity_data, provider, last_sign_in_at, created_at, updated_at)
  values (gen_random_uuid(), v_id, v_id::text,
    jsonb_build_object('sub', v_id::text, 'email', p_email, 'email_verified', true), 'email', now(), now(), now());
  update profiles set role = p_role, full_name = p_name where id = v_id;
  return v_id;
end $function$
;;
revoke execute on function _seed_user(text, text, app_role, text) from public, anon, authenticated;

insert into regions (name, delivery_fee) values
  ('Lagos Island', 5000), ('Lagos Mainland', 4000), ('Ikeja', 4500), ('Lekki-Ajah', 6000), ('Ibadan', 9000), ('Abuja', 15000);

insert into products (sku, name, unit, price, on_hand, reorder_level, min_qty, max_qty) values
  ('CEM-50', 'Cement, 50 kg bag', 'bag', 9500, 800, 150, 10, 2000),
  ('ROD-12', 'Iron rod, 12 mm', 'length', 7200, 600, 100, 5, 1500),
  ('ROD-16', 'Iron rod, 16 mm', 'length', 11800, 300, 80, 5, 1000),
  ('PNT-20W', 'Emulsion paint, white, 20 L', 'bucket', 38000, 120, 30, 1, 200),
  ('PNT-20C', 'Emulsion paint, cream, 20 L', 'bucket', 38000, 45, 30, 1, 200),
  ('TIL-6060', 'Floor tile 60x60, carton', 'carton', 14500, 400, 80, 2, 800),
  ('PVC-4', 'PVC pipe, 4 inch, 6 m', 'length', 8600, 250, 50, 2, 500),
  ('PVC-2', 'PVC pipe, 2 inch, 6 m', 'length', 4100, 9, 40, 2, 500),
  ('ROOF-AL', 'Aluminium roofing sheet, 0.55 mm', 'sheet', 12500, 350, 60, 10, 1000),
  ('NAIL-3', 'Nails, 3 inch, 25 kg', 'carton', 31000, 60, 15, 1, 100),
  ('WIRE-25', 'Electric cable, 2.5 mm, 100 m', 'roll', 52000, 70, 20, 1, 150),
  ('SAND-T', 'Sharp sand, 20 tonne trip', 'trip', 185000, 0, 2, 1, 10);

insert into vehicles (plate, description, capacity) values
  ('LSR-482-XA', '10-tonne truck', 10000), ('KJA-117-BD', 'Pickup van', 1500), ('EKY-903-AF', '5-tonne truck', 5000);

insert into screening_list (kind, value, note) values
  ('free_domain','gmail.com',null), ('free_domain','yahoo.com',null), ('free_domain','hotmail.com',null), ('free_domain','outlook.com',null),
  ('blocked_reg_no','RC-000000','Test blocked number'),
  ('preapproved_reg_no','RC-778899','Invited partner');

do $$
declare v_pw text := 'VerityDemo#2026'; d1 uuid; d2 uuid; c1 uuid; c2 uuid; u1 uuid; u2 uuid;
begin
  perform _seed_user('admin@verity.example', 'Amaka Admin', 'admin', v_pw);
  perform _seed_user('ops@verity.example', 'Olu Ops Desk', 'ops', v_pw);
  perform _seed_user('finance@verity.example', 'Funmi Finance', 'finance', v_pw);
  perform _seed_user('warehouse@verity.example', 'Wale Warehouse', 'warehouse', v_pw);
  perform _seed_user('dispatch@verity.example', 'Dayo Dispatch', 'dispatch', v_pw);
  d1 := _seed_user('driver1@verity.example', 'Chidi Driver', 'driver', v_pw);
  d2 := _seed_user('driver2@verity.example', 'Musa Driver', 'driver', v_pw);
  insert into drivers (user_id, phone, licence_no) values (d1, '08031110001', 'LAG-DL-22841'), (d2, '08031110002', 'LAG-DL-33917');
  update profiles set phone = '08031110001' where id = d1;
  update profiles set phone = '08031110002' where id = d2;

  u1 := _seed_user('buyer@adebayo.example', 'Tunde Adebayo', 'customer', v_pw);
  insert into customers (name, reg_no, contact_name, email, phone, address, industry, expected_volume, status)
  values ('Adebayo Builders Ltd', 'RC-1234567', 'Tunde Adebayo', 'buyer@adebayo.example', '08025550101',
          '14 Allen Avenue, Ikeja, Lagos', 'Construction', 40, 'active') returning id into c1;
  insert into customer_users values (u1, c1);
  insert into addresses (customer_id, label, line, region_id, instructions) values
    (c1, 'Head office', '14 Allen Avenue, Ikeja', (select id from regions where name = 'Ikeja'), 'Gate 2, ask for the store keeper'),
    (c1, 'Lekki site', 'Plot 7, Admiralty Way, Lekki Phase 1', (select id from regions where name = 'Lekki-Ajah'), 'Site office by the crane');

  u2 := _seed_user('orders@okafor.example', 'Ngozi Okafor', 'customer', v_pw);
  insert into customers (name, reg_no, contact_name, email, phone, address, industry, expected_volume, status)
  values ('Okafor Homes', 'RC-7654321', 'Ngozi Okafor', 'orders@okafor.example', '08025550202',
          '3 Ring Road, Ibadan', 'Real estate', 20, 'active') returning id into c2;
  insert into customer_users values (u2, c2);
  insert into addresses (customer_id, label, line, region_id) values
    (c2, 'Ibadan yard', '3 Ring Road, Ibadan', (select id from regions where name = 'Ibadan'));
end $$;
