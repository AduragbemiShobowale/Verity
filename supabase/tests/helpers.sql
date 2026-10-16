-- Helpers for testing workflow functions from the SQL editor as a given user.
-- Not callable from the app. Example:
--   select set_config('request.jwt.claims', _claims('admin@verity.example'), false);
--   select run_simulation(500);        -- 500 orders, rolled back, summary kept

CREATE OR REPLACE FUNCTION public._claims(p_email text)
 RETURNS text
 LANGUAGE sql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
  select json_build_object('sub', id, 'role', 'authenticated')::text from profiles where email = p_email
$function$
;
;
revoke execute on function _claims(text) from public, anon, authenticated;
