-- Undo setup_baseline_session.sql after the session and after extract_baseline.sql has been saved. NOT RUN.
-- Removes only rows that belong to the dummy customers (admin_note = 'baseline session dummy').
begin;
update settings set value = 'true' where key = 'auto_approve_enabled';
update products set active = true where sku = 'SAND-T';
create temp table b_cust as select id from customers where admin_note = 'baseline session dummy';
create temp table b_ord as select id from orders where customer_id in (select id from b_cust);
create temp table b_user as select user_id from customer_users where customer_id in (select id from b_cust);
-- stock reserved by approved baseline orders is released before the orders are removed
update products p set reserved = greatest(p.reserved - x.q, 0)
  from (select oi.product_id, sum(oi.qty_ordered) q from order_items oi join orders o on o.id = oi.order_id
        where o.id in (select id from b_ord) and o.status in ('awaiting_payment','payment_verification','paid','picking','packed') group by 1) x
  where p.id = x.product_id;
delete from notifications where order_id in (select id from b_ord);
delete from validation_results where order_id in (select id from b_ord);
delete from approvals where order_id in (select id from b_ord);
delete from invoices where order_id in (select id from b_ord);
delete from order_events where order_id in (select id from b_ord);
delete from order_items where order_id in (select id from b_ord);
delete from orders where id in (select id from b_ord);
delete from addresses where customer_id in (select id from b_cust);
delete from customer_users where customer_id in (select id from b_cust);
delete from customers where id in (select id from b_cust);
delete from auth.users where id in (select user_id from b_user);
commit;
