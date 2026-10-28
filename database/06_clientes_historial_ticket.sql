-- Compatibilidad: el código publicado ya usa estos RPC. Ejecutar después de 05.
begin;
create table if not exists public.bodega_clientes (
 id bigint generated always as identity primary key,
 dni text not null unique check(dni ~ '^[0-9]{8}$'),
 nombre text not null check(length(trim(nombre)) between 2 and 120),
 creado_en timestamptz not null default now(), actualizado_en timestamptz not null default now()
);
alter table public.bodega_ventas
 add column if not exists cliente_id bigint references public.bodega_clientes(id),
 add column if not exists cliente_dni text,
 add column if not exists cliente_nombre text,
 add column if not exists pago_referencia text,
 add column if not exists pago_entidad text,
 add column if not exists pago_validacion text,
 add column if not exists caja_payload jsonb;
create unique index if not exists bodega_ventas_referencia_unica_idx
 on public.bodega_ventas(medio_pago,upper(trim(pago_entidad)),upper(trim(pago_referencia))) where pago_referencia is not null;
create index if not exists bodega_ventas_cliente_fecha_idx on public.bodega_ventas(cliente_dni,fecha desc);
create index if not exists bodega_ventas_fecha_estado_idx on public.bodega_ventas(fecha desc,estado,id desc);
create table if not exists public.bodega_tickets (
 venta_id bigint primary key references public.bodega_ventas(id),datos jsonb not null,
 creado_en timestamptz not null default now()
);
do $migration$ begin
if to_regprocedure('public.bodega_numero_orden(bigint)') is null then execute $definition$
create function public.bodega_numero_orden(p_venta bigint) returns text language sql immutable
 set search_path=public,pg_temp as $$select 'VM-'||lpad(p_venta::text,greatest(8,length(p_venta::text)),'0')$$;
$definition$;end if;
if to_regprocedure('public.bodega_datos_ticket(bigint)') is null then execute $definition$
create function public.bodega_datos_ticket(p_venta bigint) returns jsonb language sql stable
 security definer set search_path=public,pg_temp as $$
 select jsonb_build_object('venta_id',v.id,'orden',bodega_numero_orden(v.id),'fecha',v.fecha,'fecha_hora',v.fecha_hora,
 'estado',v.estado,'origen',v.origen,'medio_pago',v.medio_pago,'total',v.total,'cliente_nombre',v.cliente_nombre,
 'cliente_dni',v.cliente_dni,'pago_referencia',v.pago_referencia,'pago_entidad',v.pago_entidad,
 'pago_validacion',v.pago_validacion,'pago_confirmado_en',v.pago_confirmado_en,
 'subtotal',(select sum(d.cantidad*d.precio_unitario) from bodega_detalle_venta d where d.venta_id=v.id),
 'descuento',(select sum(d.descuento) from bodega_detalle_venta d where d.venta_id=v.id),
 'items',(select jsonb_agg(jsonb_build_object('producto_id',d.producto_id,'codigo',p.codigo,'nombre',p.nombre,
 'cantidad',d.cantidad,'precio_unitario',d.precio_unitario,'descuento',d.descuento,'ingreso',d.ingreso) order by d.id)
 from bodega_detalle_venta d join bodega_productos p on p.id=d.producto_id where d.venta_id=v.id))
 from bodega_ventas v where v.id=p_venta
$$;
$definition$;end if;
end $migration$;
create or replace function public.bodega_registrar_venta_caja(p_operacion uuid,p_items jsonb,p_pago text,p_usuario text,
 p_pago_confirmado boolean,p_total_confirmado numeric,p_cliente jsonb,p_referencia text,p_entidad text)
returns jsonb language plpgsql security definer set search_path=public,pg_temp as $$
declare r jsonb; v bodega_ventas; v_cli bigint; v_dni text; v_nombre text; v_ref text; v_entidad text; v_payload jsonb;
begin
 v_dni=trim(coalesce(p_cliente->>'dni',''));v_nombre=regexp_replace(trim(coalesce(p_cliente->>'nombre','')),'\s+',' ','g');
 if jsonb_typeof(p_cliente) is distinct from 'object' or (v_dni<>'' and (v_dni !~ '^[0-9]{8}$' or v_nombre=''))
 or (v_nombre<>'' and length(v_nombre) not between 2 and 120) then raise exception 'Datos del cliente inválidos';end if;
 if p_pago is null or p_pago not in ('Efectivo','Yape','Plin','Tarjeta','Transferencia') then raise exception 'Medio de pago inválido';end if;
 v_ref=upper(trim(coalesce(p_referencia,'')));v_entidad=upper(regexp_replace(trim(coalesce(p_entidad,'')),'\s+',' ','g'));
 if p_pago='Efectivo' then v_ref='';v_entidad='';
 elsif v_ref !~ '^[A-Z0-9._/-]{4,100}$' or length(v_entidad) not between 1 and 60 then raise exception 'Referencia de pago requerida';end if;
 v_payload=jsonb_build_object('dni',v_dni,'nombre',v_nombre,'referencia',v_ref,'entidad',v_entidad);
 r=bodega_registrar_venta_pagada(p_operacion,p_items,p_pago,p_usuario,p_pago_confirmado,p_total_confirmado);
 select * into v from bodega_ventas where id=(r->>'venta_id')::bigint for update;
 if v.caja_payload is not null then
  if v.caja_payload<>v_payload then raise exception 'Datos de caja cambiaron';end if;
  return r||jsonb_build_object('orden',bodega_numero_orden(v.id));
 end if;
 if v_dni<>'' then
  insert into bodega_clientes(dni,nombre) values(v_dni,v_nombre)
  on conflict(dni) do update set nombre=excluded.nombre,actualizado_en=now() returning id into v_cli;
 end if;
 begin
  update bodega_ventas set cliente_id=v_cli,cliente_dni=nullif(v_dni,''),cliente_nombre=nullif(v_nombre,''),
   pago_referencia=nullif(v_ref,''),pago_entidad=nullif(v_entidad,''),pago_validacion='MANUAL_CAJA',caja_payload=v_payload where id=v.id;
 exception when unique_violation then raise exception 'Referencia de pago ya utilizada';end;
 insert into bodega_tickets(venta_id,datos) values(v.id,bodega_datos_ticket(v.id)) on conflict do nothing;
 return r||jsonb_build_object('orden',bodega_numero_orden(v.id));
end $$;
create or replace function public.bodega_buscar_ventas(p_desde date,p_hasta date,p_busqueda text,p_estado text,
 p_pago text,p_pagina integer,p_tamano integer,p_usuario text) returns jsonb
language plpgsql security definer set search_path=public,pg_temp as $$
declare q text=lower(trim(coalesce(p_busqueda,'')));n bigint;rows jsonb;
begin
 if p_desde is null or p_hasta is null or p_desde>p_hasta or p_pagina is null or p_pagina<0
 or p_tamano is null or p_tamano not between 1 and 100 or length(q)>120
 or coalesce(p_estado,'') not in ('TODOS','COMPLETADA','ANULADA') or coalesce(p_pago,'') not in
 ('Todos','Efectivo','Yape','Plin','Tarjeta','Transferencia','Fiado') then raise exception 'Filtros de ventas inválidos';end if;
 with filtered as (select v.*,bodega_numero_orden(v.id) as orden from bodega_ventas v
 where fecha between p_desde and p_hasta and (p_estado='TODOS' or estado=p_estado)
 and (p_pago='Todos' or medio_pago=p_pago) and (q='' or strpos(lower(concat_ws(' ',v.id::text,bodega_numero_orden(v.id),
 v.cliente_nombre,v.cliente_dni,v.ticket_externo)),q)>0)),
 paged as (select * from filtered order by fecha desc,fecha_hora desc,id desc limit p_tamano offset p_pagina::bigint*p_tamano)
 select (select count(*) from filtered),coalesce(jsonb_agg(to_jsonb(paged) order by fecha desc,fecha_hora desc,id desc),'[]'::jsonb)
 into n,rows from paged;
 return jsonb_build_object('total',n,'rows',rows);
end $$;
create or replace function public.bodega_ticket_venta(p_venta bigint,p_usuario text) returns jsonb language plpgsql
security definer set search_path=public,pg_temp as $$
declare data jsonb;estado_actual text;
begin
 select estado into estado_actual from bodega_ventas where id=p_venta;
 if not found then raise exception 'Venta no encontrada';end if;
 select datos into data from bodega_tickets where venta_id=p_venta;
 if not found then data=bodega_datos_ticket(p_venta)||jsonb_build_object('datos_reconstruidos',true);end if;
 return data||jsonb_build_object('estado',estado_actual);
end $$;
alter table public.bodega_clientes enable row level security;
alter table public.bodega_tickets enable row level security;
revoke all on public.bodega_clientes,public.bodega_tickets from public,anon,authenticated;
grant all on public.bodega_clientes,public.bodega_tickets to service_role;
grant usage,select on sequence public.bodega_clientes_id_seq to service_role;
revoke all on function public.bodega_numero_orden(bigint),public.bodega_datos_ticket(bigint),
 public.bodega_registrar_venta_caja(uuid,jsonb,text,text,boolean,numeric,jsonb,text,text),
 public.bodega_buscar_ventas(date,date,text,text,text,integer,integer,text),public.bodega_ticket_venta(bigint,text) from public,anon,authenticated;
grant execute on function public.bodega_numero_orden(bigint),public.bodega_datos_ticket(bigint),
 public.bodega_registrar_venta_caja(uuid,jsonb,text,text,boolean,numeric,jsonb,text,text),
 public.bodega_buscar_ventas(date,date,text,text,text,integer,integer,text),public.bodega_ticket_venta(bigint,text) to service_role;
notify pgrst,'reload schema';
commit;
