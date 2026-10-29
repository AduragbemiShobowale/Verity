-- Baseline session setup for the Verity condition. NOT RUN. Run once, as the database owner, on the morning of the session.
-- Creates one dummy login per fictional customer in the pack (password below), the two saved addresses, the account
-- status shown in the customer register, four earlier delivered orders per customer (as in the simulation, so the
-- unusual-quantity rule has a history), and the orders listed in orders_already_received.csv as submitted this morning.
-- It also turns automatic approval off and marks SAND-T discontinued for the session. cleanup_baseline_session.sql undoes it.
-- All addresses use the reserved .example domain. No real customer is touched.
do $$
declare
  r record; uid uuid; cid uuid; addr uuid; o uuid; k int; it text; items jsonb;
  pw text := 'Baseline#2026';
begin
  update settings set value = 'false' where key = 'auto_approve_enabled';
  update products set active = false where sku = 'SAND-T';
  for r in select * from (values
    ('Adeyemi & Sons Construction Ltd', 'Folake Adeyemi', 'folake.adeyemi@adeyemi1.example', '08030104729', '11 Main Road, Ikeja', 'Plot 101, Ikeja', 'Ikeja', 'active'),
    ('Agege Steel Works', 'Yusuf Adebanjo', 'yusuf.adebanjo@agege13.example', '08031361477', '23 Main Road, Ikeja', 'Plot 113, Ikeja', 'Ikeja', 'active'),
    ('Ajah Sunrise Housing Co-op', 'Blessing Okoro', 'blessing.okoro@ajah14.example', '08031466206', '24 Main Road, Lekki-Ajah', 'Plot 114, Lekki-Ajah', 'Lekki-Ajah', 'active'),
    ('Apapa Port Works Supplies', 'Garba Usman', 'garba.usman@apapa20.example', '08032094580', '30 Main Road, Lagos Mainland', 'Plot 120, Lagos Mainland', 'Lagos Mainland', 'active'),
    ('Bodija Interiors', 'Segun Olatunji', 'segun.olatunji@bodija16.example', '08031675664', '26 Main Road, Ibadan', 'Plot 116, Ibadan', 'Ibadan', 'active'),
    ('Eko Bridge Contractors', 'Tolulope Ogunleye', 'tolulope.ogunleye@eko6.example', '08030628374', '16 Main Road, Lagos Island', 'Plot 106, Lagos Island', 'Lagos Island', 'active'),
    ('Greenfield Estates Nigeria', 'Ngozi Eze', 'ngozi.eze@greenfield7.example', '08030733103', '17 Main Road, Lekki-Ajah', 'Plot 107, Lekki-Ajah', 'Lekki-Ajah', 'active'),
    ('Gwarinpa Homes Ltd', 'Fatima Sani', 'fatima.sani@gwarinpa15.example', '08031570935', '25 Main Road, Abuja', 'Plot 115, Abuja', 'Abuja', 'active'),
    ('Ibadan Prime Homes Ltd', 'Oluwaseun Afolabi', 'oluwaseun.afolabi@ibadan3.example', '08030314187', '13 Main Road, Ibadan', 'Plot 103, Ibadan', 'Ibadan', 'active'),
    ('Kanu Brothers Building Supplies', 'Chukwuemeka Kanu', 'chukwuemeka.kanu@kanu2.example', '08030209458', '12 Main Road, Lagos Mainland', 'Plot 102, Lagos Mainland', 'Lagos Mainland', 'active'),
    ('Lekki Coastal Developers', 'Amina Bello', 'amina.bello@lekki4.example', '08030418916', '14 Main Road, Lekki-Ajah', 'Plot 104, Lekki-Ajah', 'Lekki-Ajah', 'active'),
    ('Magodo Residential Ltd', 'Funmilayo Adeleke', 'funmilayo.adeleke@magodo19.example', '08031989851', '29 Main Road, Ikeja', 'Plot 119, Ikeja', 'Ikeja', 'active'),
    ('Marina Point Facilities', 'Kemi Lawson', 'kemi.lawson@marina11.example', '08031152019', '21 Main Road, Lagos Island', 'Plot 111, Lagos Island', 'Lagos Island', 'blocked'),
    ('Northgate Realty Abuja', 'Ibrahim Musa', 'ibrahim.musa@northgate5.example', '08030523645', '15 Main Road, Abuja', 'Plot 105, Abuja', 'Abuja', 'active'),
    ('Ola-Ade Hardware & Tiles', 'Babatunde Oladipo', 'babatunde.oladipo@olaade8.example', '08030837832', '18 Main Road, Ikeja', 'Plot 108, Ikeja', 'Ikeja', 'active'),
    ('Oyo Central Builders', 'Adewale Akinyemi', 'adewale.akinyemi@oyo10.example', '08031047290', '20 Main Road, Ibadan', 'Plot 110, Ibadan', 'Ibadan', 'active'),
    ('Surulere Paint & Finish', 'Uche Nwosu', 'uche.nwosu@surulere12.example', '08031256748', '22 Main Road, Lagos Mainland', 'Plot 112, Lagos Mainland', 'Lagos Mainland', 'active'),
    ('Victoria Island Fit-Out Ltd', 'Chiamaka Obi', 'chiamaka.obi@victoria17.example', '08031780393', '27 Main Road, Lagos Island', 'Plot 117, Lagos Island', 'Lagos Island', 'active'),
    ('Yaba Tech Hub Builders', 'Emeka Okafor', 'emeka.okafor@yaba18.example', '08031885122', '28 Main Road, Lagos Mainland', 'Plot 118, Lagos Mainland', 'Lagos Mainland', 'active'),
    ('Zuma Rock Engineering', 'Hauwa Abdullahi', 'hauwa.abdullahi@zuma9.example', '08030942561', '19 Main Road, Abuja', 'Plot 109, Abuja', 'Abuja', 'on_hold')
  ) v(company, contact, email, phone, addr1, addr2, region, status) loop
    uid := _seed_user(r.email, r.contact, 'customer', pw);
    insert into customers (name, reg_no, contact_name, email, phone, address, industry, expected_volume, status, admin_note)
    values (r.company, 'RC-BASE-' || substr(md5(r.email), 1, 6), r.contact, r.email, r.phone, r.addr1, 'Construction', 20, 'active', 'baseline session dummy')
    returning id into cid;
    insert into customer_users values (uid, cid);
    insert into addresses (customer_id, label, line, region_id) values
      (cid, 'Head office', r.addr1, (select id from regions where name = r.region)),
      (cid, 'Site', r.addr2, (select id from regions where name = r.region));
    perform _as(r.email);
    addr := (select id from addresses where customer_id = cid and label = 'Head office');
    for k in 1..4 loop
      o := save_draft(null, jsonb_build_object('address_id', addr, 'requested_date', current_date + 3, 'notes', 'baseline history',
             'items', jsonb_build_array(jsonb_build_object('product_id', (select id from products where sku = 'CEM-50'), 'qty', 20 + k),
                                        jsonb_build_object('product_id', (select id from products where sku = 'ROD-12'), 'qty', 10 + k))));
      perform submit_order(o, true);
      -- history only: move it out of the approval queue and the 24-hour duplicate window
      update orders set status = 'delivered', submitted_at = now() - interval '14 days' where id = o;
    end loop;
    update customers set status = r.status::customer_status where id = cid;
  end loop;
  -- orders already received this morning (the reference log), so repeats can be recognised
  for r in select * from (values
    ('Apapa Port Works Supplies', 'TIL-6060 x 90; NAIL-3 x 7; PVC-4 x 28'),
    ('Ibadan Prime Homes Ltd', 'CEM-50 x 117'),
    ('Gwarinpa Homes Ltd', 'ROD-12 x 143; ROD-16 x 37'),
    ('Gwarinpa Homes Ltd', 'NAIL-3 x 13'),
    ('Yaba Tech Hub Builders', 'ROD-16 x 21; CEM-50 x 119; ROOF-AL x 59'),
    ('Agege Steel Works', 'WIRE-25 x 7; PNT-20C x 1; NAIL-3 x 8'),
    ('Gwarinpa Homes Ltd', 'TIL-6060 x 3; PNT-20C x 2'),
    ('Yaba Tech Hub Builders', 'CEM-50 x 77; ROD-16 x 27')
  ) v(company, lines) loop
    cid := (select id from customers where name = r.company and admin_note = 'baseline session dummy');
    perform _as((select email from customers where id = cid));
    items := '[]';
    foreach it in array string_to_array(r.lines, '; ') loop
      items := items || jsonb_build_array(jsonb_build_object('product_id', (select id from products where sku = split_part(it, ' x ', 1)),
                                                             'qty', split_part(it, ' x ', 2)::numeric));
    end loop;
    o := save_draft(null, jsonb_build_object('address_id', (select id from addresses where customer_id = cid and label = 'Head office'),
           'requested_date', current_date + 3, 'notes', 'baseline earlier order', 'items', items));
    perform submit_order(o, true);
  end loop;
end $$;
