-- Ejecutar una vez en el SQL Editor del mismo Supabase, después de 01/03/04.
-- Actualización aditiva: conserva ventas, productos, existencias y auditoría.
begin;
alter table public.bodega_ventas
 add column if not exists pago_confirmado_en timestamptz,
 add column if not exists pago_confirmado_por text,
 add column if not exists pago_confirmado_total numeric(12,2);

create or replace function public.bodega_registrar_venta_pagada(
 p_operacion uuid, p_items jsonb, p_pago text, p_usuario text,
 p_pago_confirmado boolean, p_total_confirmado numeric
) returns jsonb language plpgsql security definer set search_path = public as $$
declare resultado jsonb; venta_id bigint;
begin
 if p_pago_confirmado is distinct from true or p_total_confirmado is null then
  raise exception 'Confirma el pago completo antes de registrar la venta';
 end if;
 if p_total_confirmado::text in ('NaN','Infinity','-Infinity') or
    p_total_confirmado < 0 or p_total_confirmado <> round(p_total_confirmado,2) then
  raise exception 'Importe de pago confirmado inválido';
 end if;
 -- La función existente bloquea artículos, comprueba stock y conserva la misma
 -- operación al reintentar. Ambas llamadas pertenecen a esta transacción.
 resultado := public.bodega_registrar_venta(p_operacion,p_items,p_pago,p_usuario);
 if (resultado->>'total')::numeric <> p_total_confirmado then
  -- Si cambió un precio, se revierte TODO, incluso venta, stock y operación.
  raise exception 'El total cambió. Revisa el carrito y confirma el pago nuevamente';
 end if;
 venta_id := (resultado->>'venta_id')::bigint;
 update public.bodega_ventas set
  pago_confirmado_en = coalesce(pago_confirmado_en,now()),
  pago_confirmado_por = coalesce(pago_confirmado_por,p_usuario),
  pago_confirmado_total = coalesce(pago_confirmado_total,p_total_confirmado)
 where id = venta_id;
 return resultado;
end; $$;

revoke all on function public.bodega_registrar_venta_pagada(uuid,jsonb,text,text,boolean,numeric) from public, anon, authenticated;
grant execute on function public.bodega_registrar_venta_pagada(uuid,jsonb,text,text,boolean,numeric) to service_role;
notify pgrst, 'reload schema';
commit;
