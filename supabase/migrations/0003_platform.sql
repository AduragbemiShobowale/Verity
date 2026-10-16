-- Verity: privileges, schedules, realtime and file storage

-- Nothing is callable without signing in; internal helpers are not callable at all.
revoke execute on all functions in schema public from public, anon;
grant execute on all functions in schema public to authenticated;
alter default privileges in schema public revoke execute on functions from anon, public;
revoke all on all tables in schema public from anon;
alter default privileges in schema public revoke all on tables from anon;
revoke all on all sequences in schema public from anon;
grant select on simulation_runs to authenticated;

revoke execute on function _err(text), _require(app_role[]), _transition(uuid, order_status, text),
  _notify_user(uuid, text, text, text, uuid, text, boolean), _notify_role(app_role, text, text, text, uuid, text, boolean),
  _notify_customer(uuid, text, text, text, uuid, text, boolean), _order_no(uuid), _recalc_order(uuid),
  _check_low_stock(uuid), _release_reservation(uuid, text), _restock_picked(uuid, text), _amount_paid(uuid),
  _amount_refunded(uuid), _raise_refund(uuid, numeric, text), _issue_code(uuid), _pack(uuid, text),
  _validate(uuid), _vr(uuid, text, severity, text, text), _approve(uuid, text), _cancel(uuid, text),
  _snapshot_item(), _as(text), audit(text, text, text, jsonb, jsonb), expire_payment_windows(), scheduled_alerts(),
  handle_new_user(), audit_trigger()
  from authenticated;

-- Unpaid orders are cancelled when the window closes (paused while Finance checks a proof).
select cron.schedule('verity-expire-payments', '*/5 * * * *', 'select public.expire_payment_windows()');
select cron.schedule('verity-alerts', '17 * * * *', 'select public.scheduled_alerts()');

-- Live notification bell
alter publication supabase_realtime add table notifications;

-- Private buckets; files live under <user id>/...
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types) values
  ('registration-docs', 'registration-docs', false, 5242880, array['application/pdf','image/jpeg','image/png']),
  ('payment-proofs', 'payment-proofs', false, 5242880, array['application/pdf','image/jpeg','image/png'])
on conflict (id) do nothing;

create policy "own uploads" on storage.objects for insert to authenticated
  with check (bucket_id in ('registration-docs','payment-proofs') and (storage.foldername(name))[1] = auth.uid()::text);
create policy "own files" on storage.objects for select to authenticated
  using (bucket_id in ('registration-docs','payment-proofs') and (storage.foldername(name))[1] = auth.uid()::text);
create policy "admin reads registration docs" on storage.objects for select to authenticated
  using (bucket_id = 'registration-docs' and public.has_role('admin'));
create policy "finance reads payment proofs" on storage.objects for select to authenticated
  using (bucket_id = 'payment-proofs' and public.has_role('finance','ops','admin'));
