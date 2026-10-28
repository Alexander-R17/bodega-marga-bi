-- Ejecutar después de 09. Actualización aditiva: no elimina ventas ni inventario.
begin;

create or replace function public.bodega_buscar_clientes(p_busqueda text,p_usuario text)
returns jsonb language plpgsql stable security definer set search_path=public,pg_temp as $$
declare q text=lower(trim(coalesce(p_busqueda,'')));r jsonb;
begin
 if length(q)>120 or coalesce(trim(p_usuario),'')='' then raise exception 'Datos del cliente inválidos';end if;
 select coalesce(jsonb_agg(to_jsonb(c) order by nombre,id),'[]'::jsonb) into r from
 (select id,dni,nombre from bodega_clientes where q='' or strpos(lower(nombre||' '||dni),q)>0
 order by nombre,id limit 75)c;
 return r;
end $$;

-- Asegura los nuevos cobros antes de abrir la espera; nunca simula un celular conectado.
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
 if not exists(select 1 from bodega_pago_dispositivos where id=p_dispositivo and activo
 and ultimo_contacto between now()-interval '20 minutes' and now()+interval '5 seconds') then
 raise exception 'El celular receptor no tiene una conexión reciente';end if;
 if (coalesce(p_cliente->>'dni','')<>'' and (p_cliente->>'dni' !~ '^[0-9]{8}$' or length(trim(coalesce(p_cliente->>'nombre',''))) not between 2 and 120))
 then raise exception 'Datos del cliente inválidos';end if;
 if p_id is null or jsonb_typeof(p_items) is distinct from 'array' or jsonb_array_length(p_items) not between 1 and 100
 or jsonb_typeof(p_cliente) is distinct from 'object' or p_total is null or p_total not between 0.01 and 100000 or p_total<>round(p_total,2) then raise exception 'Cobro inválido';end if;
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
-- La evidencia es un aviso del dispositivo, no una respuesta del banco.
-- La misma cerradura de receptor que usa la ingestión evita nuevas inserciones
-- durante la comprobación final y la transacción de venta.
create or replace function public.bodega_confirmar_cobro_aviso(p_id uuid,p_usuario text)
returns jsonb language plpgsql security definer set search_path=public,pg_temp as $$
declare receptor uuid;c bodega_cobros;a bodega_pago_avisos;s jsonb;r jsonb;ref text;espera integer;
begin
 select dispositivo_id into receptor from bodega_cobros where id=p_id and usuario_uid=p_usuario;
 if not found then raise exception 'Cobro no encontrado';end if;
 perform id from bodega_pago_dispositivos where id=receptor for update;
 select * into c from bodega_cobros where id=p_id for update;
 if c.estado='REGISTRADO' then
  return jsonb_build_object('estado','REGISTRADO','venta_id',c.venta_id,'total',c.importe_centimos/100.0,'orden',bodega_numero_orden(c.venta_id));
 end if;
 s=bodega_estado_cobro(p_id,p_usuario);
 if s->>'estado'<>'DETECTADO' then raise exception 'La orden no tiene un aviso único';end if;
 select * into c from bodega_cobros where id=p_id;
 select * into a from bodega_pago_avisos where id=c.aviso_id for update;
 if a.id is null or a.dispositivo_id<>receptor or a.importe_centimos<>c.importe_centimos
 or a.paquete<>'com.bcp.innovacxion.yapeapp'
 or a.notificado_en<c.creado_en or a.notificado_en>c.vence_en or a.recibido_en<c.creado_en
 or a.recibido_en-a.notificado_en not between interval '-5 seconds' and interval '30 seconds'
 then raise exception 'El aviso requiere conciliación';end if;
 -- Breve margen de observación para detectar dos pagos iguales en la misma ventana.
 espera=greatest(0,ceil(extract(epoch from(a.recibido_en+interval '5 seconds'-now())))::integer);
 if espera>0 then return jsonb_build_object('estado','DETECTADO','segundos_confirmacion',espera);end if;
 ref='AVISO-YAPE-'||a.id::text;
 r=bodega_registrar_venta_caja(c.id,c.items,'Yape',p_usuario,true,c.importe_centimos/100.0,c.cliente,ref,'YAPE DEL NEGOCIO');
 update bodega_ventas set pago_validacion='AVISO_DISPOSITIVO' where id=(r->>'venta_id')::bigint;
 -- El identificador técnico no se presenta como código de operación bancaria.
 update bodega_tickets set datos=datos||jsonb_build_object('pago_validacion','AVISO_DISPOSITIVO',
  'aviso_id',a.id,'dispositivo_id',receptor,'cobro_id',c.id)
 where venta_id=(r->>'venta_id')::bigint;
 update bodega_cobros set estado='REGISTRADO',venta_id=(r->>'venta_id')::bigint where id=c.id;
 return jsonb_build_object('estado','REGISTRADO','venta_id',(r->>'venta_id')::bigint,
 'total',c.importe_centimos/100.0,'orden',bodega_numero_orden((r->>'venta_id')::bigint));
end $$;

-- Repara concesiones solo a servidor; no desactiva RLS ni concede acceso público.
grant usage on schema public to service_role;
do $$ declare t record;f record;
begin
 for t in select c.oid::regclass as tabla from pg_class c join pg_namespace n on n.oid=c.relnamespace
 where n.nspname='public' and c.relkind in ('r','p') and c.relname like 'bodega\_%' escape '\' loop
  execute format('alter table %s enable row level security',t.tabla);
  execute format('revoke all on table %s from public,anon,authenticated',t.tabla);
  execute format('grant select,insert,update,delete on table %s to service_role',t.tabla);
 end loop;
 for t in select c.oid::regclass as secuencia from pg_class c join pg_namespace n on n.oid=c.relnamespace
 where n.nspname='public' and c.relkind='S' and c.relname like 'bodega\_%' escape '\' loop
  execute format('revoke all on sequence %s from public,anon,authenticated',t.secuencia);
  execute format('grant usage,select on sequence %s to service_role',t.secuencia);
 end loop;
 for f in select p.oid::regprocedure as firma from pg_proc p join pg_namespace n on n.oid=p.pronamespace
 where n.nspname='public' and p.prokind='f' and p.proname like 'bodega\_%' escape '\' loop
  execute format('revoke all on function %s from public,anon,authenticated',f.firma);
  execute format('grant execute on function %s to service_role',f.firma);
 end loop;
end $$;

-- Sin SECURITY DEFINER: comprueba el rol real que llegó a PostgREST.
create or replace function public.bodega_diagnostico_caja(p_usuario text)
returns jsonb language plpgsql stable set search_path=public,pg_temp as $$
declare ok boolean;permisos jsonb;
begin
 if coalesce(trim(p_usuario),'')='' then raise exception 'Usuario requerido';end if;
 permisos=jsonb_build_object('ventas',(has_table_privilege(current_user,'public.bodega_ventas','INSERT') and has_table_privilege(current_user,'public.bodega_ventas','UPDATE')),
 'clientes',(has_table_privilege(current_user,'public.bodega_clientes','SELECT') and has_table_privilege(current_user,'public.bodega_clientes','INSERT') and has_table_privilege(current_user,'public.bodega_clientes','UPDATE')),
 'tickets',(has_table_privilege(current_user,'public.bodega_tickets','INSERT') and has_table_privilege(current_user,'public.bodega_tickets','UPDATE')),
 'avisos',has_table_privilege(current_user,'public.bodega_pago_avisos','SELECT'),
 'venta_caja',has_function_privilege(current_user,'public.bodega_registrar_venta_caja(uuid,jsonb,text,text,boolean,numeric,jsonb,text,text)','EXECUTE'),
 'cobro_aviso',has_function_privilege(current_user,'public.bodega_confirmar_cobro_aviso(uuid,text)','EXECUTE'));
 select bool_and(value::boolean) into ok from jsonb_each_text(permisos);
 return jsonb_build_object('ok',ok and current_user='service_role','rol_servidor',current_user,
 'version_caja',10,'permisos',permisos);
end $$;
revoke all on function public.bodega_diagnostico_caja(text) from public,anon,authenticated;
grant execute on function public.bodega_diagnostico_caja(text) to service_role;
notify pgrst,'reload schema';
commit;
