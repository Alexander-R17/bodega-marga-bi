-- Crédito comercial sin intereses. Ejecutar después de 06. No crea datos de ejemplo.
begin;
alter table public.bodega_ventas drop constraint if exists bodega_ventas_medio_pago_check;
alter table public.bodega_ventas add constraint bodega_ventas_medio_pago_check
 check(medio_pago in ('Efectivo','Yape','Plin','Tarjeta','Transferencia','Fiado'));
create table if not exists public.bodega_fiado_cuentas (
 id bigint generated always as identity primary key,
 cliente_id bigint not null unique references public.bodega_clientes(id),
 limite numeric(12,2) not null check(limite between 0 and 1000000),
 activo boolean not null default true,creado_por text not null,creado_en timestamptz not null default now()
);
create table if not exists public.bodega_fiado_cargos (
 venta_id bigint primary key references public.bodega_ventas(id),
 cuenta_id bigint not null references public.bodega_fiado_cuentas(id),
 importe numeric(12,2) not null check(importe between 0.01 and 1000000),
 vencimiento date not null,creado_en timestamptz not null default now()
);
create index if not exists bodega_fiado_cuenta_idx on public.bodega_fiado_cargos(cuenta_id,venta_id);
create table if not exists public.bodega_fiado_abonos (
 id uuid primary key,venta_id bigint not null references public.bodega_fiado_cargos(venta_id),
 importe numeric(12,2) not null check(importe between 0.01 and 1000000),
 medio_pago text not null check(medio_pago in ('Efectivo','Yape','Plin','Tarjeta','Transferencia')),
 pago_referencia text,pago_entidad text,usuario_uid text not null,creado_en timestamptz not null default now(),
 anulado_en timestamptz,anulado_por text,motivo_anulacion text
);
create index if not exists bodega_fiado_abonos_venta_idx on public.bodega_fiado_abonos(venta_id);

-- Una referencia no puede utilizarse para una venta y también para un abono.
create table if not exists public.bodega_referencias_pago (
 medio text not null,entidad text not null,referencia text not null,
 origen text not null,origen_id text not null,primary key(medio,entidad,referencia)
);
insert into public.bodega_referencias_pago
 select medio_pago,upper(trim(pago_entidad)),upper(trim(pago_referencia)),'VENTA',id::text
 from public.bodega_ventas where pago_referencia is not null on conflict do nothing;
create or replace function public.bodega_reservar_referencia() returns trigger language plpgsql
security definer set search_path=public,pg_temp as $$
declare tipo text;registro bodega_referencias_pago;
begin
 if new.pago_referencia is null then return new;end if;
 tipo=case when tg_table_name='bodega_ventas' then 'VENTA' else 'ABONO' end;
 insert into bodega_referencias_pago values(new.medio_pago,upper(trim(new.pago_entidad)),upper(trim(new.pago_referencia)),tipo,new.id::text)
 on conflict do nothing;
 select * into registro from bodega_referencias_pago where medio=new.medio_pago and entidad=upper(trim(new.pago_entidad)) and referencia=upper(trim(new.pago_referencia));
 if registro.origen<>tipo or registro.origen_id<>new.id::text then raise exception 'Referencia de pago ya utilizada';end if;
 return new;
end $$;
drop trigger if exists bodega_referencia_venta on public.bodega_ventas;
create trigger bodega_referencia_venta before insert or update of pago_referencia,pago_entidad,medio_pago on public.bodega_ventas
 for each row execute function public.bodega_reservar_referencia();
drop trigger if exists bodega_referencia_abono on public.bodega_fiado_abonos;
create trigger bodega_referencia_abono before insert on public.bodega_fiado_abonos
 for each row execute function public.bodega_reservar_referencia();

create or replace function public.bodega_saldo_fiado(p_cuenta bigint) returns numeric language sql stable
security definer set search_path=public,pg_temp as $$
 select coalesce(sum(c.importe-coalesce((select sum(a.importe) from bodega_fiado_abonos a
 where a.venta_id=c.venta_id and a.anulado_en is null),0)),0)
 from bodega_fiado_cargos c join bodega_ventas v on v.id=c.venta_id where c.cuenta_id=p_cuenta and v.estado='COMPLETADA'
$$;
create or replace function public.bodega_configurar_fiado(p_dni text,p_nombre text,p_limite numeric,p_activo boolean,p_usuario text)
returns jsonb language plpgsql security definer set search_path=public,pg_temp as $$
declare cli bigint;cuenta bigint;
begin
 if coalesce(p_dni,'') !~ '^[0-9]{8}$' or length(trim(coalesce(p_nombre,''))) not between 2 and 120
 or p_limite is null or p_limite not between 0 and 1000000 or p_limite<>round(p_limite,2) or p_activo is null then
 raise exception 'Datos de cuenta de fiado inválidos';end if;
 insert into bodega_clientes(dni,nombre) values(p_dni,trim(p_nombre)) on conflict(dni)
 do update set nombre=excluded.nombre,actualizado_en=now() returning id into cli;
 insert into bodega_fiado_cuentas(cliente_id,limite,activo,creado_por) values(cli,p_limite,p_activo,p_usuario)
 on conflict(cliente_id) do update set limite=excluded.limite,activo=excluded.activo returning id into cuenta;
 return jsonb_build_object('cuenta_id',cuenta);
end $$;
create or replace function public.bodega_vender_fiado(p_operacion uuid,p_items jsonb,p_cuenta bigint,p_vencimiento date,
 p_total_confirmado numeric,p_usuario text) returns jsonb language plpgsql security definer set search_path=public,pg_temp as $$
declare cuenta bodega_fiado_cuentas;cliente bodega_clientes;cargo bodega_fiado_cargos;r jsonb;vid bigint;total numeric;saldo numeric;
begin
 select * into cuenta from bodega_fiado_cuentas where id=p_cuenta for update;
 if not found then raise exception 'Cuenta de fiado no encontrada';end if;
 r=bodega_registrar_venta(p_operacion,p_items,'Fiado',p_usuario);vid=(r->>'venta_id')::bigint;total=(r->>'total')::numeric;
 if p_total_confirmado is null or p_total_confirmado<>total then raise exception 'El total cambió. Revisa el carrito y confirma el pago nuevamente';end if;
 select * into cargo from bodega_fiado_cargos where venta_id=vid;
 if found then
  if cargo.cuenta_id<>p_cuenta or cargo.vencimiento is distinct from p_vencimiento then raise exception 'Operación reutilizada con otros datos';end if;
  return r||jsonb_build_object('orden',bodega_numero_orden(vid));
 end if;
 if not cuenta.activo then raise exception 'Cuenta de fiado bloqueada';end if;
 if total<=0 or p_vencimiento is null or p_vencimiento<(now() at time zone 'America/Lima')::date
 or p_vencimiento>(now() at time zone 'America/Lima')::date+365 then raise exception 'Fecha de fiado inválida';end if;
 saldo=bodega_saldo_fiado(p_cuenta);
 if saldo+total>cuenta.limite then raise exception 'Límite de fiado insuficiente';end if;
 if exists(select 1 from bodega_fiado_cargos c join bodega_ventas v on v.id=c.venta_id where c.cuenta_id=p_cuenta
  and v.estado='COMPLETADA' and c.vencimiento<(now() at time zone 'America/Lima')::date and
  c.importe>coalesce((select sum(a.importe) from bodega_fiado_abonos a where a.venta_id=c.venta_id and a.anulado_en is null),0)) then
  raise exception 'El cliente tiene fiado vencido';end if;
 select * into cliente from bodega_clientes where id=cuenta.cliente_id;
 insert into bodega_fiado_cargos(venta_id,cuenta_id,importe,vencimiento) values(vid,p_cuenta,total,p_vencimiento);
 update bodega_ventas set cliente_id=cliente.id,cliente_dni=cliente.dni,cliente_nombre=cliente.nombre,pago_validacion='CREDITO_FIADO' where id=vid;
 insert into bodega_tickets(venta_id,datos) values(vid,bodega_datos_ticket(vid)||jsonb_build_object('fiado_vencimiento',p_vencimiento));
 return r||jsonb_build_object('orden',bodega_numero_orden(vid));
end $$;

create or replace function public.bodega_abonar_fiado(p_id uuid,p_venta bigint,p_importe numeric,p_pago text,p_referencia text,
 p_entidad text,p_confirmado boolean,p_usuario text) returns jsonb language plpgsql security definer set search_path=public,pg_temp as $$
declare cargo bodega_fiado_cargos;venta bodega_ventas;anterior bodega_fiado_abonos;saldo numeric;ref text;entidad text;
begin
 ref=nullif(upper(trim(p_referencia)),'');entidad=nullif(upper(trim(p_entidad)),'');
 if p_pago='Efectivo' then ref=null;entidad=null;end if;
 if p_confirmado is distinct from true or p_id is null or p_importe is null or p_importe not between 0.01 and 1000000
 or p_importe<>round(p_importe,2) or coalesce(p_pago,'') not in ('Efectivo','Yape','Plin','Tarjeta','Transferencia') then
 raise exception 'Abono de fiado inválido';end if;
 if p_pago<>'Efectivo' and (coalesce(ref,'') !~ '^[A-Z0-9._/-]{4,100}$' or length(coalesce(entidad,'')) not between 1 and 60) then
 raise exception 'Referencia de pago requerida';end if;
 select * into cargo from bodega_fiado_cargos where venta_id=p_venta;
 if not found then raise exception 'Venta de fiado no encontrada';end if;
 perform id from bodega_fiado_cuentas where id=cargo.cuenta_id for update;
 select * into venta from bodega_ventas where id=p_venta for update;
 select * into anterior from bodega_fiado_abonos where id=p_id;
 if found then
  if anterior.venta_id<>p_venta or anterior.importe<>p_importe or anterior.medio_pago<>p_pago or
  anterior.pago_referencia is distinct from ref or anterior.pago_entidad is distinct from entidad or anterior.usuario_uid<>p_usuario then
  raise exception 'Operación reutilizada con otros datos';end if;
  return jsonb_build_object('abono_id',p_id,'importe',p_importe);
 end if;
 if venta.estado<>'COMPLETADA' then raise exception 'La venta está anulada';end if;
 select cargo.importe-coalesce(sum(importe),0) into saldo from bodega_fiado_abonos where venta_id=p_venta and anulado_en is null;
 if p_importe>saldo then raise exception 'El abono supera la deuda pendiente';end if;
 insert into bodega_fiado_abonos(id,venta_id,importe,medio_pago,pago_referencia,pago_entidad,usuario_uid)
 values(p_id,p_venta,p_importe,p_pago,ref,entidad,p_usuario);
 return jsonb_build_object('abono_id',p_id,'importe',p_importe,'saldo_venta',saldo-p_importe);
end $$;
create or replace function public.bodega_anular_abono(p_id uuid,p_motivo text,p_usuario text) returns jsonb
language plpgsql security definer set search_path=public,pg_temp as $$
declare a bodega_fiado_abonos;cuenta bigint;
begin
 if length(trim(coalesce(p_motivo,'')))<3 then raise exception 'Motivo requerido';end if;
 select c.cuenta_id into cuenta from bodega_fiado_abonos a join bodega_fiado_cargos c on c.venta_id=a.venta_id where a.id=p_id;
 if not found then raise exception 'Abono no encontrado';end if;
 perform id from bodega_fiado_cuentas where id=cuenta for update;
 select * into a from bodega_fiado_abonos where id=p_id for update;
 if a.anulado_en is not null and (a.anulado_por<>p_usuario or a.motivo_anulacion<>trim(p_motivo)) then raise exception 'Operación reutilizada con otros datos';end if;
 update bodega_fiado_abonos set anulado_en=coalesce(anulado_en,now()),anulado_por=p_usuario,motivo_anulacion=trim(p_motivo) where id=p_id;
 return jsonb_build_object('abono_id',p_id,'anulado',true);
end $$;
create or replace function public.bodega_proteger_fiado() returns trigger language plpgsql security definer set search_path=public,pg_temp as $$
begin
 if new.estado='ANULADA' and old.estado<>'ANULADA' and exists(select 1 from bodega_fiado_abonos where venta_id=new.id and anulado_en is null) then
 raise exception 'Anula primero los abonos del fiado y concilia la devolución';end if;
 return new;
end $$;
drop trigger if exists bodega_proteger_fiado on public.bodega_ventas;
create trigger bodega_proteger_fiado before update of estado on public.bodega_ventas for each row execute function public.bodega_proteger_fiado();

create or replace function public.bodega_consultar_fiado(p_busqueda text,p_cuenta bigint,p_usuario text) returns jsonb language plpgsql
security definer set search_path=public,pg_temp as $$
declare cuentas jsonb;cargos jsonb;abonos jsonb;
begin
 select coalesce(jsonb_agg(to_jsonb(t)),'[]'::jsonb) into cuentas from
 (select c.id,cl.dni,cl.nombre,c.limite,c.activo,bodega_saldo_fiado(c.id) as saldo from bodega_fiado_cuentas c
 join bodega_clientes cl on cl.id=c.cliente_id where strpos(lower(cl.dni||' '||cl.nombre),lower(left(coalesce(p_busqueda,''),120)))>0 order by cl.nombre,c.id limit 100)t;
 select coalesce(jsonb_agg(to_jsonb(t)),'[]'::jsonb) into cargos from
 (select c.venta_id,bodega_numero_orden(c.venta_id) as orden,v.fecha,c.importe,c.vencimiento,v.estado,
 c.importe-coalesce((select sum(a.importe) from bodega_fiado_abonos a where a.venta_id=c.venta_id and a.anulado_en is null),0) as saldo
 from bodega_fiado_cargos c join bodega_ventas v on v.id=c.venta_id where c.cuenta_id=p_cuenta order by v.fecha desc,c.venta_id desc limit 250)t;
 select coalesce(jsonb_agg(to_jsonb(t)),'[]'::jsonb) into abonos from
 (select a.* from bodega_fiado_abonos a join bodega_fiado_cargos c on c.venta_id=a.venta_id where c.cuenta_id=p_cuenta order by a.creado_en desc,a.id limit 250)t;
 return jsonb_build_object('cuentas',cuentas,'cargos',cargos,'abonos',abonos);
end $$;
create or replace function public.bodega_ticket_venta(p_venta bigint,p_usuario text) returns jsonb language plpgsql
security definer set search_path=public,pg_temp as $$
declare data jsonb;estado_actual text;c bodega_fiado_cargos;abonado numeric;
begin
 select estado into estado_actual from bodega_ventas where id=p_venta;
 if not found then raise exception 'Venta no encontrada';end if;
 select datos into data from bodega_tickets where venta_id=p_venta;
 if not found then data=bodega_datos_ticket(p_venta)||jsonb_build_object('datos_reconstruidos',true);end if;
 select * into c from bodega_fiado_cargos where venta_id=p_venta;
 if found then
  select coalesce(sum(importe),0) into abonado from bodega_fiado_abonos where venta_id=p_venta and anulado_en is null;
  data=data||jsonb_build_object('fiado_vencimiento',c.vencimiento,'fiado_abonado',abonado,'fiado_saldo',case when estado_actual='ANULADA' then 0 else c.importe-abonado end);
 end if;
 return data||jsonb_build_object('estado',estado_actual);
end $$;
create or replace function public.bodega_resumen_fiado(p_desde date,p_hasta date,p_usuario text) returns jsonb language plpgsql
security definer set search_path=public,pg_temp as $$
declare emitido numeric;cobrado numeric;cartera numeric;vencido numeric;serie jsonb;
begin
 if p_desde is null or p_hasta is null or p_desde>p_hasta or p_hasta-p_desde>366 then raise exception 'Período de fiado inválido';end if;
 select coalesce(sum(c.importe),0) into emitido from bodega_fiado_cargos c join bodega_ventas v on v.id=c.venta_id
 where v.estado='COMPLETADA' and v.fecha between p_desde and p_hasta;
 select coalesce(sum(a.importe),0) into cobrado from bodega_fiado_abonos a join bodega_ventas v on v.id=a.venta_id
 where a.anulado_en is null and v.estado='COMPLETADA' and (a.creado_en at time zone 'America/Lima')::date between p_desde and p_hasta;
 select coalesce(sum(c.importe-coalesce((select sum(a.importe) from bodega_fiado_abonos a where a.venta_id=c.venta_id and a.anulado_en is null),0)),0),
 coalesce(sum(case when c.vencimiento<(now() at time zone 'America/Lima')::date then c.importe-coalesce((select sum(a.importe) from bodega_fiado_abonos a where a.venta_id=c.venta_id and a.anulado_en is null),0) else 0 end),0)
 into cartera,vencido from bodega_fiado_cargos c join bodega_ventas v on v.id=c.venta_id where v.estado='COMPLETADA';
 select coalesce(jsonb_agg(to_jsonb(t) order by fecha),'[]'::jsonb) into serie from (
 select fecha,sum(credito) as credito,sum(abonos) as abonos from (
  select v.fecha,c.importe as credito,0::numeric as abonos from bodega_fiado_cargos c join bodega_ventas v on v.id=c.venta_id
  where v.estado='COMPLETADA' and v.fecha between p_desde and p_hasta
  union all select (a.creado_en at time zone 'America/Lima')::date,0::numeric,a.importe from bodega_fiado_abonos a
  join bodega_ventas v on v.id=a.venta_id where a.anulado_en is null and v.estado='COMPLETADA'
  and (a.creado_en at time zone 'America/Lima')::date between p_desde and p_hasta
 ) movimientos group by fecha)t;
 return jsonb_build_object('credito_periodo',emitido,'abonos_periodo',cobrado,'cartera_actual',cartera,'vencido_actual',vencido,'serie',serie);
end $$;
do $$declare t text;f record;begin
 foreach t in array array['bodega_fiado_cuentas','bodega_fiado_cargos','bodega_fiado_abonos','bodega_referencias_pago'] loop
 execute format('alter table public.%I enable row level security',t);
 execute format('revoke all on public.%I from public,anon,authenticated',t);
 execute format('grant all on public.%I to service_role',t);end loop;
 for f in select p.oid::regprocedure as sig from pg_proc p join pg_namespace n on n.oid=p.pronamespace
 where n.nspname='public' and p.proname in ('bodega_reservar_referencia','bodega_saldo_fiado','bodega_configurar_fiado','bodega_vender_fiado',
 'bodega_abonar_fiado','bodega_anular_abono','bodega_proteger_fiado','bodega_consultar_fiado','bodega_resumen_fiado') loop
 execute format('revoke all on function %s from public,anon,authenticated',f.sig);
 execute format('grant execute on function %s to service_role',f.sig);end loop;
end $$;
grant usage,select on sequence public.bodega_fiado_cuentas_id_seq to service_role;
notify pgrst,'reload schema';
commit;
