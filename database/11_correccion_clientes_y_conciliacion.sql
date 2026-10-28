-- Ejecutar después de las migraciones ya instaladas. No borra registros ni registra ventas al ejecutarse.
-- Corrige 42702 al vender con DNI y añade recuperación explícita de cobros recibidos.
begin;
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
-- Mantiene evidencia de quién recuperó una orden que ya había recibido un aviso.
alter table public.bodega_cobros add column if not exists conciliado_en timestamptz,
 add column if not exists conciliado_por text;

create or replace function public.bodega_cobros_por_conciliar(p_usuario text)
returns jsonb language sql stable security definer set search_path=public,pg_temp as $$
 select coalesce(jsonb_agg(to_jsonb(p) order by creado_en desc),'[]'::jsonb) from
 (select c.id,c.importe_centimos,c.creado_en,c.estado,c.aviso_id,c.items,
 coalesce(nullif(c.cliente->>'nombre',''),'Consumidor final') as cliente
 from bodega_cobros c where c.usuario_uid=p_usuario and c.venta_id is null and c.aviso_id is not null
 and c.estado in ('DETECTADO','VENCIDO','CANCELADO') order by c.creado_en desc limit 50)p
$$;

create or replace function public.bodega_conciliar_cobro_recibido(p_id uuid,p_revisado boolean,p_usuario text)
returns jsonb language plpgsql security definer set search_path=public,pg_temp as $$
declare receptor uuid;activo boolean;c bodega_cobros;a bodega_pago_avisos;r jsonb;cantidad integer;
begin
 if p_revisado is distinct from true then raise exception 'Revisa el movimiento recibido antes de conciliar';end if;
 select dispositivo_id into receptor from bodega_cobros where id=p_id and usuario_uid=p_usuario;
 if not found then raise exception 'Cobro no encontrado';end if;
 select d.activo into activo from bodega_pago_dispositivos d where d.id=receptor for update;
 select * into c from bodega_cobros where id=p_id and usuario_uid=p_usuario for update;
 if c.estado='REGISTRADO' and c.venta_id is not null then
  return jsonb_build_object('estado','REGISTRADO','venta_id',c.venta_id,'total',c.importe_centimos/100.0,'orden',bodega_numero_orden(c.venta_id));
 end if;
 if not activo then raise exception 'Receptor no autorizado';end if;
 if c.estado not in ('DETECTADO','VENCIDO','CANCELADO') or c.aviso_id is null or c.venta_id is not null then
  raise exception 'La orden no tiene un aviso recibido para conciliar';end if;
 select * into a from bodega_pago_avisos where id=c.aviso_id for update;
 if a.id is null or a.dispositivo_id<>c.dispositivo_id or a.importe_centimos<>c.importe_centimos
 or a.paquete<>'com.bcp.innovacxion.yapeapp' or a.notificado_en<c.creado_en
 or a.notificado_en>c.vence_en or a.recibido_en<c.creado_en
 or a.recibido_en-a.notificado_en not between interval '-5 seconds' and interval '30 seconds'
 then raise exception 'El aviso no cumple las condiciones de la orden original';end if;
 if exists(select 1 from bodega_cobros otro where otro.id<>c.id and otro.aviso_id=a.id) then
  raise exception 'El aviso ya está asociado a otra orden';end if;
 select count(*) into cantidad from bodega_pago_avisos candidato
 where candidato.dispositivo_id=c.dispositivo_id and candidato.importe_centimos=c.importe_centimos
 and candidato.recibido_en>=c.creado_en
 and candidato.notificado_en between c.creado_en-interval '5 seconds' and c.vence_en
 and not exists(select 1 from bodega_cobros otro where otro.id<>c.id and otro.aviso_id=candidato.id);
 if cantidad<>1 then raise exception 'Hay varios avisos para esta orden; requiere revisión adicional';end if;
 -- Reutiliza el UUID original: una sola venta, un descuento de stock y una referencia única.
 r=bodega_registrar_venta_caja(c.id,c.items,'Yape',p_usuario,true,c.importe_centimos/100.0,c.cliente,
  'AVISO-YAPE-'||a.id::text,'YAPE DEL NEGOCIO');
 update bodega_ventas set pago_validacion='AVISO_DISPOSITIVO' where id=(r->>'venta_id')::bigint;
 update bodega_tickets set datos=datos||jsonb_build_object('pago_validacion','AVISO_DISPOSITIVO',
  'aviso_id',a.id,'dispositivo_id',c.dispositivo_id,'cobro_id',c.id,
  'conciliado_por',p_usuario,'conciliado_en',now(),'conciliacion_manual',true)
 where venta_id=(r->>'venta_id')::bigint;
 update bodega_cobros set estado='REGISTRADO',venta_id=(r->>'venta_id')::bigint,
  conciliado_por=p_usuario,conciliado_en=now() where id=c.id;
 return jsonb_build_object('estado','REGISTRADO','venta_id',(r->>'venta_id')::bigint,'total',c.importe_centimos/100.0,
 'orden',bodega_numero_orden((r->>'venta_id')::bigint));
end $$;
-- Un aviso ya asociado no desaparece al vencer el tiempo de espera del cliente.
create or replace function public.bodega_estado_cobro(p_id uuid,p_usuario text) returns jsonb language plpgsql
security definer set search_path=public,pg_temp as $$
declare c bodega_cobros;cantidad integer;aviso bigint;activo boolean;
begin
 select * into c from bodega_cobros where id=p_id for update;
 if not found or c.usuario_uid<>p_usuario then raise exception 'Cobro no encontrado';end if;
 if c.estado in ('ESPERANDO','DETECTADO','AMBIGUO') then
  select d.activo into activo from bodega_pago_dispositivos d where d.id=c.dispositivo_id;
  if not activo then c.estado='CANCELADO';
  elsif c.vence_en<=now() and c.aviso_id is null then c.estado='VENCIDO';
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
revoke all on function public.bodega_registrar_venta_caja(uuid,jsonb,text,text,boolean,numeric,jsonb,text,text),
 public.bodega_estado_cobro(uuid,text),public.bodega_cobros_por_conciliar(text),
 public.bodega_conciliar_cobro_recibido(uuid,boolean,text) from public,anon,authenticated;
grant execute on function public.bodega_registrar_venta_caja(uuid,jsonb,text,text,boolean,numeric,jsonb,text,text),
 public.bodega_estado_cobro(uuid,text),public.bodega_cobros_por_conciliar(text),
 public.bodega_conciliar_cobro_recibido(uuid,boolean,text) to service_role;
notify pgrst,'reload schema';
commit;
