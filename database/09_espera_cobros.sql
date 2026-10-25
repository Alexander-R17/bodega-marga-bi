-- Ejecutar después de 07 y 08. La asociación del aviso no certifica el abono bancario.
begin;
create table if not exists public.bodega_cobros (
 id uuid primary key,dispositivo_id uuid not null references public.bodega_pago_dispositivos(id),
 items jsonb not null,cliente jsonb not null,importe_centimos integer not null check(importe_centimos>0),
 usuario_uid text not null,creado_en timestamptz not null default now(),vence_en timestamptz not null default(now()+interval '2 minutes'),
 estado text not null default 'ESPERANDO' check(estado in ('ESPERANDO','DETECTADO','AMBIGUO','CANCELADO','VENCIDO','REGISTRADO')),
 aviso_id bigint unique references public.bodega_pago_avisos(id),venta_id bigint unique references public.bodega_ventas(id)
);
create unique index if not exists bodega_cobro_activo_receptor_idx on public.bodega_cobros(dispositivo_id)
 where estado in ('ESPERANDO','DETECTADO','AMBIGUO');
create index if not exists bodega_avisos_receptor_hora_idx on public.bodega_pago_avisos(dispositivo_id,recibido_en);
create or replace function public.bodega_abrir_cobro(p_id uuid,p_dispositivo uuid,p_items jsonb,p_cliente jsonb,p_total numeric,p_usuario text)
returns jsonb language plpgsql security definer set search_path=public,pg_temp as $$
declare c bodega_cobros;calculado numeric;cantidad integer;
begin
 perform id from bodega_pago_dispositivos where id=p_dispositivo and activo for update;
 if not found then raise exception 'Receptor no autorizado';end if;
 select * into c from bodega_cobros where id=p_id;
 if found then
  if c.dispositivo_id<>p_dispositivo or c.items<>p_items or c.cliente<>p_cliente or c.usuario_uid<>p_usuario or c.importe_centimos<>p_total*100 then
  raise exception 'Operación reutilizada con otros datos';end if;
  return to_jsonb(c)-'items'-'cliente';
 end if;
 update bodega_cobros set estado='VENCIDO' where dispositivo_id=p_dispositivo and estado in ('ESPERANDO','DETECTADO','AMBIGUO') and vence_en<=now();
 if exists(select 1 from bodega_cobros where dispositivo_id=p_dispositivo and estado in ('ESPERANDO','DETECTADO','AMBIGUO')) then raise exception 'El receptor ya tiene un cobro pendiente';end if;
 if p_id is null or jsonb_typeof(p_items) is distinct from 'array' or jsonb_array_length(p_items) not between 1 and 100
 or jsonb_typeof(p_cliente) is distinct from 'object' or p_total is null or p_total not between 0.01 and 100000 then raise exception 'Cobro inválido';end if;
 select sum((x->>'cantidad')::integer*p.precio-(x->>'descuento')::numeric),count(*) into calculado,cantidad
 from jsonb_array_elements(p_items)x join bodega_productos p on p.id=(x->>'producto_id')::bigint
 where p.activo and (x->>'cantidad')::integer between 1 and p.stock and (x->>'descuento')::numeric between 0 and (x->>'cantidad')::integer*p.precio
 and (x->>'descuento')::numeric=round((x->>'descuento')::numeric,2);
 if cantidad<>jsonb_array_length(p_items) or cantidad<>(select count(distinct x->>'producto_id') from jsonb_array_elements(p_items)x)
 or calculado is distinct from p_total then raise exception 'El total cambió. Revisa el carrito y confirma el pago nuevamente';end if;
 insert into bodega_cobros(id,dispositivo_id,items,cliente,importe_centimos,usuario_uid)
 values(p_id,p_dispositivo,p_items,p_cliente,(p_total*100)::integer,p_usuario) returning * into c;
 return to_jsonb(c)-'items'-'cliente';
end $$;
create or replace function public.bodega_estado_cobro(p_id uuid,p_usuario text) returns jsonb language plpgsql
security definer set search_path=public,pg_temp as $$
declare c bodega_cobros;cantidad integer;aviso bigint;activo boolean;
begin
 select * into c from bodega_cobros where id=p_id for update;
 if not found or c.usuario_uid<>p_usuario then raise exception 'Cobro no encontrado';end if;
 if c.estado in ('ESPERANDO','DETECTADO','AMBIGUO') then
  select d.activo into activo from bodega_pago_dispositivos d where d.id=c.dispositivo_id;
  if not activo then c.estado='CANCELADO';
  elsif c.vence_en<=now() then c.estado='VENCIDO';
  else
   select count(*),min(a.id) into cantidad,aviso from bodega_pago_avisos a
   where a.dispositivo_id=c.dispositivo_id and a.importe_centimos=c.importe_centimos
   and a.recibido_en>=c.creado_en and a.notificado_en between c.creado_en-interval '5 seconds' and c.vence_en
   and not exists(select 1 from bodega_cobros otro where otro.aviso_id=a.id and otro.id<>c.id);
   c.estado=case when cantidad=0 then 'ESPERANDO' when cantidad=1 then 'DETECTADO' else 'AMBIGUO' end;
   c.aviso_id=case when cantidad=1 then aviso else null end;
  end if;
  update bodega_cobros set estado=c.estado,aviso_id=c.aviso_id where id=c.id;
 end if;
 return jsonb_build_object('id',c.id,'estado',c.estado,'importe_centimos',c.importe_centimos,
 'segundos_restantes',greatest(0,ceil(extract(epoch from(c.vence_en-now())))),'aviso_id',c.aviso_id,'venta_id',c.venta_id);
end $$;
create or replace function public.bodega_finalizar_cobro(p_id uuid,p_accion text,p_referencia text,p_entidad text,p_revisado boolean,p_usuario text)
returns jsonb language plpgsql security definer set search_path=public,pg_temp as $$
declare c bodega_cobros;r jsonb;estado_actual jsonb;
begin
 select * into c from bodega_cobros where id=p_id for update;
 if not found or c.usuario_uid<>p_usuario then raise exception 'Cobro no encontrado';end if;
 if p_accion='CANCELAR' then
  if c.estado='REGISTRADO' then raise exception 'La venta ya fue registrada';end if;
  update bodega_cobros set estado='CANCELADO' where id=c.id;return jsonb_build_object('estado','CANCELADO');
 end if;
 if p_accion is distinct from 'REGISTRAR' or p_revisado is distinct from true then raise exception 'Comprueba el abono antes de registrar';end if;
 if c.estado<>'REGISTRADO' then
  estado_actual=bodega_estado_cobro(p_id,p_usuario);
  if estado_actual->>'estado'<>'DETECTADO' then raise exception 'El cobro requiere revisión';end if;
 end if;
 r=bodega_registrar_venta_caja(c.id,c.items,'Yape',p_usuario,true,c.importe_centimos/100.0,c.cliente,p_referencia,p_entidad);
 update bodega_cobros set estado='REGISTRADO',venta_id=(r->>'venta_id')::bigint where id=c.id;
 return r;
end $$;
alter table public.bodega_cobros enable row level security;
revoke all on public.bodega_cobros from public,anon,authenticated;
grant all on public.bodega_cobros to service_role;
revoke all on function public.bodega_abrir_cobro(uuid,uuid,jsonb,jsonb,numeric,text),public.bodega_estado_cobro(uuid,text),
 public.bodega_finalizar_cobro(uuid,text,text,text,boolean,text) from public,anon,authenticated;
grant execute on function public.bodega_abrir_cobro(uuid,uuid,jsonb,jsonb,numeric,text),public.bodega_estado_cobro(uuid,text),
 public.bodega_finalizar_cobro(uuid,text,text,text,boolean,text) to service_role;
notify pgrst,'reload schema';
commit;
