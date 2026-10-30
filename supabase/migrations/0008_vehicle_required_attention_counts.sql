-- Dispatch must choose a vehicle as well as a driver, and staff menus show
-- how many items need a person. delivery_codes is not readable by staff,
-- so the open code problems are worked out here.

create or replace function public.assign_delivery(p_orders uuid[], p_driver uuid, p_vehicle integer)
 returns integer
 language plpgsql
 security definer
 set search_path to 'public'
as $function$
declare v uuid; v_status order_status; n int := 0; v_list text := '';
begin
  perform _require('dispatch');
  if not exists (select 1 from profiles p join drivers d on d.user_id = p.id
                 where p.id = p_driver and p.role = 'driver' and p.status = 'active' and d.active) then
    perform _err('Choose an active driver.');
  end if;
  if p_vehicle is null then
    perform _err('Choose a vehicle as well as a driver.');
  end if;
  if not exists (select 1 from vehicles where id = p_vehicle and active) then
    perform _err('Choose an active vehicle.');
  end if;
  foreach v in array p_orders loop
    select status into v_status from orders where id = v for update;
    if v_status is null or v_status not in ('packed','delivery_failed') then
      perform _err(format('%s is not ready for dispatch.', coalesce(_order_no(v), 'An order')));
    end if;
    update deliveries set current = false, outcome = coalesce(outcome, 'reassigned') where order_id = v and current;
    insert into deliveries (order_id, driver_id, vehicle_id, assigned_by) values (v, p_driver, p_vehicle, auth.uid());
    if not exists (select 1 from delivery_codes where order_id = v and expires_at > now() and not locked and used_at is null) then
      perform _issue_code(v);
    end if;
    perform _transition(v, 'assigned', 'Assigned to driver');
    v_list := v_list || _order_no(v) || ' ';
    n := n + 1;
  end loop;
  perform _notify_user(p_driver, 'assigned', format('%s new deliver%s', n, case when n = 1 then 'y' else 'ies' end),
                       trim(v_list), null, '/driver');
  return n;
end $function$;

-- Order ids per kind of open item. A locked or expired code stops counting
-- once Ops re-issues it, because _issue_code clears the lock.
create or replace function public.attention_summary()
 returns jsonb
 language plpgsql
 stable
 security definer
 set search_path to 'public'
as $function$
begin
  if not has_role('ops', 'dispatch', 'admin') then
    perform _err('Not allowed.');
  end if;
  return jsonb_build_object(
    'code_problems', coalesce((select jsonb_agg(o.id) from orders o join delivery_codes c on c.order_id = o.id
       where o.status = 'out_for_delivery' and c.used_at is null and (c.locked or c.expires_at <= now())), '[]'),
    'escalations', coalesce((select jsonb_agg(o.id) from orders o where o.status = 'payment_rejected'
       and exists (select 1 from notifications n where n.order_id = o.id and n.event = 'payment_escalation')), '[]'),
    'cancel_requests', coalesce((select jsonb_agg(id) from orders where cancel_requested_reason is not null and status <> 'cancelled'), '[]'),
    'failed', coalesce((select jsonb_agg(id) from orders where status = 'delivery_failed'), '[]'),
    'to_assign', coalesce((select jsonb_agg(id) from orders where status = 'packed'), '[]')
  );
end $function$;

revoke execute on function public.attention_summary() from public, anon;
grant execute on function public.attention_summary() to authenticated;
