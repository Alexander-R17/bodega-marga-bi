-- Bodega Marga BI | ejecutar completo en Supabase SQL Editor.
-- Migración aditiva: no modifica ni elimina tablas del campus.
begin;

create table if not exists public.bodega_categorias (
 id bigint generated always as identity primary key,
 nombre text not null unique check (length(trim(nombre)) between 1 and 80)
);
create table if not exists public.bodega_proveedores (
 id bigint generated always as identity primary key,
 nombre text not null unique check (length(trim(nombre)) between 1 and 100)
);
create table if not exists public.bodega_productos (
 id bigint generated always as identity primary key,
 codigo text not null unique check (length(trim(codigo)) between 1 and 60),
 nombre text not null check (length(trim(nombre)) between 1 and 120),
 categoria_id bigint not null references public.bodega_categorias(id),
 proveedor_id bigint not null references public.bodega_proveedores(id),
 precio numeric(12,2) not null check (precio >= 0),
 costo numeric(12,2) not null check (costo >= 0),
 stock integer not null default 0 check (stock >= 0),
 stock_minimo integer not null default 5 check (stock_minimo >= 0),
 plazo_dias integer not null default 2 check (plazo_dias between 0 and 90),
 activo boolean not null default true,
 creado_en timestamptz not null default now()
);
create table if not exists public.bodega_tiempo (
 fecha date primary key,
 anio integer not null, mes integer not null, dia integer not null,
 dia_semana integer not null
);
create table if not exists public.bodega_lotes (
 id uuid primary key,
 nombre text not null, hash_archivo text not null unique,
 filas integer not null check (filas between 1 and 2000),
 estado text not null default 'VALIDADO' check (estado in ('VALIDADO','PROCESADO')),
 usuario_uid text not null,
 creado_en timestamptz not null default now(), procesado_en timestamptz
);
create table if not exists public.bodega_staging (
 id bigint generated always as identity primary key,
 lote_id uuid not null references public.bodega_lotes(id),
 numero integer not null, payload jsonb not null,
 unique(lote_id,numero)
);
create table if not exists public.bodega_ventas (
 id bigint generated always as identity primary key,
 fecha_hora timestamptz not null default now(),
 fecha date not null references public.bodega_tiempo(fecha),
 medio_pago text not null check (medio_pago in ('Efectivo','Yape','Plin','Tarjeta','Transferencia')),
 origen text not null check (origen in ('POS','HISTORICO')),
 ticket_externo text unique,
 lote_id uuid references public.bodega_lotes(id),
 usuario_uid text not null,
 estado text not null default 'COMPLETADA' check (estado in ('COMPLETADA','ANULADA')),
 total numeric(14,2) not null default 0 check (total >= 0)
);
create table if not exists public.bodega_detalle_venta (
 id bigint generated always as identity primary key,
 venta_id bigint not null references public.bodega_ventas(id),
 producto_id bigint not null references public.bodega_productos(id),
 cantidad integer not null check (cantidad > 0),
 precio_unitario numeric(12,2) not null check (precio_unitario >= 0),
 costo_unitario numeric(12,2) not null check (costo_unitario >= 0),
 descuento numeric(14,2) not null default 0 check (descuento between 0 and cantidad*precio_unitario),
 ingreso numeric(14,2) generated always as (cantidad*precio_unitario-descuento) stored,
 margen_bruto numeric(14,2) generated always as (cantidad*(precio_unitario-costo_unitario)-descuento) stored,
 unique(venta_id,producto_id)
);
create table if not exists public.bodega_movimientos (
 id bigint generated always as identity primary key,
 producto_id bigint not null references public.bodega_productos(id),
 fecha_hora timestamptz not null default now(),
 tipo text not null check (tipo in ('ENTRADA','VENTA','AJUSTE','MERMA','ANULACION')),
 variacion integer not null,
 stock_resultante integer not null check (stock_resultante >= 0),
 costo_unitario numeric(12,2) not null check (costo_unitario >= 0),
 motivo text not null, venta_id bigint references public.bodega_ventas(id),
 usuario_uid text not null
);
create table if not exists public.bodega_operaciones (
 id uuid primary key, tipo text not null, payload jsonb not null,
 usuario_uid text not null, resultado jsonb,
 creado_en timestamptz not null default now()
);
create table if not exists public.bodega_predicciones (
 id bigint generated always as identity primary key,
 producto_id bigint not null references public.bodega_productos(id),
 fecha date not null, corte date not null,
 unidades numeric(12,3) not null check (unidades >= 0),
 metodo text not null,
 wape_validacion double precision check (wape_validacion >= 0),
 wape_baseline double precision check (wape_baseline >= 0),
 usuario_uid text not null, creado_en timestamptz not null default now(),
 check (fecha > corte), unique(producto_id,fecha,corte)
);
create table if not exists public.bodega_eventos (
 id bigint generated always as identity primary key,
 fecha_hora timestamptz not null default now(), usuario_uid text not null,
 evento text not null, detalle text not null default ''
);
create table if not exists public.bodega_reposiciones (
 id uuid primary key,
 producto_id bigint not null references public.bodega_productos(id),
 unidades integer not null check (unidades > 0),
 decision text not null check (decision in ('ACEPTADA','DESCARTADA')),
 motivo text not null check (length(trim(motivo)) between 3 and 200),
 contexto jsonb not null,
 usuario_uid text not null,
 fecha_hora timestamptz not null default now()
);
create index if not exists bodega_ventas_fecha_idx on public.bodega_ventas(fecha);
create index if not exists bodega_detalle_producto_idx on public.bodega_detalle_venta(producto_id);
create index if not exists bodega_movimientos_producto_idx on public.bodega_movimientos(producto_id,fecha_hora);

create or replace function public.bodega_asegurar_fecha(p_fecha date) returns void
language sql set search_path = public, pg_temp as $$
 insert into public.bodega_tiempo values (p_fecha,extract(year from p_fecha)::integer,
 extract(month from p_fecha)::integer,extract(day from p_fecha)::integer,
 extract(isodow from p_fecha)::integer) on conflict do nothing;
$$;

create or replace function public.bodega_guardar_producto(p_producto jsonb) returns jsonb
language plpgsql set search_path = public, pg_temp as $$
declare c bigint; v bigint; p bigint;
begin
 insert into public.bodega_categorias(nombre) values(trim(p_producto->>'categoria'))
 on conflict(nombre) do update set nombre=excluded.nombre returning id into c;
 insert into public.bodega_proveedores(nombre) values(trim(p_producto->>'proveedor'))
 on conflict(nombre) do update set nombre=excluded.nombre returning id into v;
 if (p_producto->>'id') is null then
  insert into public.bodega_productos(codigo,nombre,categoria_id,proveedor_id,precio,costo,stock_minimo,plazo_dias,activo)
  values(trim(p_producto->>'codigo'),trim(p_producto->>'nombre'),c,v,
   (p_producto->>'precio')::numeric,(p_producto->>'costo')::numeric,
   (p_producto->>'stock_minimo')::integer,(p_producto->>'plazo_dias')::integer,
   (p_producto->>'activo')::boolean) returning id into p;
 else
  update public.bodega_productos set codigo=trim(p_producto->>'codigo'),nombre=trim(p_producto->>'nombre'),
   categoria_id=c,proveedor_id=v,precio=(p_producto->>'precio')::numeric,costo=(p_producto->>'costo')::numeric,
   stock_minimo=(p_producto->>'stock_minimo')::integer,plazo_dias=(p_producto->>'plazo_dias')::integer,
   activo=(p_producto->>'activo')::boolean where id=(p_producto->>'id')::bigint returning id into p;
  if not found then raise exception 'Código desconocido'; end if;
 end if;
 return jsonb_build_object('producto_id',p);
end $$;

create or replace function public.bodega_registrar_venta(
 p_operacion uuid,p_items jsonb,p_pago text,p_usuario text) returns jsonb
language plpgsql set search_path = public, pg_temp as $$
declare op public.bodega_operaciones; item jsonb; prod public.bodega_productos;
 payload jsonb; venta bigint; qty integer; disc numeric; fecha_local date;
 v_resultado jsonb; importe numeric;
begin
 payload:=jsonb_build_object('items',p_items,'pago',p_pago);
 insert into public.bodega_operaciones(id,tipo,payload,usuario_uid)
 values(p_operacion,'VENTA',payload,p_usuario) on conflict do nothing;
 select * into op from public.bodega_operaciones where id=p_operacion for update;
 if op.tipo<>'VENTA' or op.payload<>payload or op.usuario_uid<>p_usuario then
  raise exception 'Operación reutilizada con otros datos';
 end if;
 if op.resultado is not null then return op.resultado; end if;
 if jsonb_typeof(p_items)<>'array' or jsonb_array_length(p_items) not between 1 and 100 then
  raise exception 'Cantidad inválida';
 end if;
 if (select count(distinct (x->>'producto_id')::bigint) from jsonb_array_elements(p_items) x)
  <>jsonb_array_length(p_items) then raise exception 'Cantidad inválida: producto repetido'; end if;
 -- Bloqueo ordenado para evitar vender la misma existencia simultáneamente.
 perform id from public.bodega_productos where id in
  (select (x->>'producto_id')::bigint from jsonb_array_elements(p_items) x) order by id for update;
 fecha_local := (now() at time zone 'America/Lima')::date;
 perform public.bodega_asegurar_fecha(fecha_local);
 insert into public.bodega_ventas(fecha,medio_pago,origen,usuario_uid)
 values(fecha_local,p_pago,'POS',p_usuario) returning id into venta;
 for item in select value from jsonb_array_elements(p_items) loop
  select * into prod from public.bodega_productos where id=(item->>'producto_id')::bigint;
  if not found then raise exception 'Código desconocido'; end if;
  if not prod.activo then raise exception 'Producto inactivo'; end if;
  qty:=(item->>'cantidad')::integer; disc:=(item->>'descuento')::numeric;
  if qty is null or qty<=0 or disc is null or disc<0 or disc>qty*prod.precio then
   raise exception 'Cantidad inválida'; end if;
  if disc<>round(disc,2) then raise exception 'Precio inválido'; end if;
  if prod.stock<qty then raise exception 'Stock insuficiente para %',prod.codigo; end if;
  insert into public.bodega_detalle_venta(venta_id,producto_id,cantidad,precio_unitario,costo_unitario,descuento)
  values(venta,prod.id,qty,prod.precio,prod.costo,disc);
  update public.bodega_productos set stock=stock-qty where id=prod.id;
  insert into public.bodega_movimientos(producto_id,tipo,variacion,stock_resultante,costo_unitario,motivo,venta_id,usuario_uid)
  values(prod.id,'VENTA',-qty,prod.stock-qty,prod.costo,'Venta POS',venta,p_usuario);
 end loop;
 select sum(ingreso) into importe from public.bodega_detalle_venta where venta_id=venta;
 update public.bodega_ventas set total=importe where id=venta;
 v_resultado:=jsonb_build_object('venta_id',venta,'total',importe);
 update public.bodega_operaciones set resultado=v_resultado where id=p_operacion;
 return v_resultado;
end $$;

create or replace function public.bodega_registrar_movimiento(p_operacion uuid,p_producto bigint,
 p_tipo text,p_cantidad integer,p_costo numeric,p_motivo text,p_usuario text) returns jsonb
language plpgsql set search_path = public, pg_temp as $$
declare op public.bodega_operaciones; prod public.bodega_productos; payload jsonb;
 delta integer; nuevo integer; nuevo_costo numeric; v_resultado jsonb;
begin
 payload:=jsonb_build_object('producto',p_producto,'tipo',p_tipo,'cantidad',p_cantidad,'costo',p_costo,'motivo',p_motivo);
 insert into public.bodega_operaciones(id,tipo,payload,usuario_uid)
 values(p_operacion,'MOVIMIENTO',payload,p_usuario) on conflict do nothing;
 select * into op from public.bodega_operaciones where id=p_operacion for update;
 if op.tipo<>'MOVIMIENTO' or op.payload<>payload or op.usuario_uid<>p_usuario then
  raise exception 'Operación reutilizada con otros datos'; end if;
 if op.resultado is not null then return op.resultado; end if;
 if length(trim(coalesce(p_motivo,'')))<3 then raise exception 'Motivo requerido'; end if;
 if p_tipo not in ('ENTRADA','AJUSTE','MERMA') or p_tipo is null or p_cantidad is null or
  p_costo is null or p_costo<0 or p_costo<>round(p_costo,2) or p_cantidad<0 then raise exception 'Cantidad inválida'; end if;
 select * into prod from public.bodega_productos where id=p_producto for update;
 if not found then raise exception 'Código desconocido'; end if;
 if p_tipo='AJUSTE' then delta:=p_cantidad-prod.stock;
 elsif p_tipo='MERMA' then delta:=-p_cantidad; else delta:=p_cantidad; end if;
 if delta=0 then raise exception 'No hay cambios'; end if;
 nuevo:=prod.stock+delta;
 if nuevo<0 then raise exception 'Stock insuficiente'; end if;
 nuevo_costo:=prod.costo;
 if p_tipo='ENTRADA' then
  nuevo_costo:=round((prod.stock*prod.costo+p_cantidad*p_costo)/nuevo,2);
 end if;
 update public.bodega_productos set stock=nuevo,costo=nuevo_costo where id=p_producto;
 insert into public.bodega_movimientos(producto_id,tipo,variacion,stock_resultante,costo_unitario,motivo,usuario_uid)
 values(p_producto,p_tipo,delta,nuevo,p_costo,p_motivo,p_usuario);
 v_resultado:=jsonb_build_object('stock',nuevo,'costo',nuevo_costo);
 update public.bodega_operaciones set resultado=v_resultado where id=p_operacion;
 return v_resultado;
end $$;

create or replace function public.bodega_crear_lote(p_id uuid,p_nombre text,p_hash text,p_filas jsonb,p_usuario text)
returns jsonb language plpgsql set search_path=public,pg_temp as $$
declare lote public.bodega_lotes; item jsonb; n integer:=0;
begin
 if jsonb_typeof(p_filas)<>'array' or jsonb_array_length(p_filas) not between 1 and 2000
  or length(p_hash)<>64 then raise exception 'Lote no válido'; end if;
 -- Hash previene cargar dos veces el mismo archivo, incluso con un UUID nuevo.
 insert into public.bodega_lotes(id,nombre,hash_archivo,filas,usuario_uid)
 values(p_id,p_nombre,p_hash,jsonb_array_length(p_filas),p_usuario) on conflict do nothing;
 select * into lote from public.bodega_lotes where hash_archivo=p_hash for update;
 if not found then raise exception 'Lote no válido'; end if;
 if lote.id<>p_id then return jsonb_build_object('lote_id',lote.id,'estado',lote.estado); end if;
 if not exists(select 1 from public.bodega_staging where lote_id=p_id) then
  for item in select value from jsonb_array_elements(p_filas) loop
   n:=n+1;
   insert into public.bodega_staging(lote_id,numero,payload) values(p_id,n,item);
  end loop;
 end if;
 return jsonb_build_object('lote_id',lote.id,'estado',lote.estado);
end $$;

create or replace function public.bodega_procesar_lote(p_lote uuid,p_usuario text) returns jsonb
language plpgsql set search_path=public,pg_temp as $$
declare lote public.bodega_lotes; fila record; prod public.bodega_productos;
 venta bigint; f date; ticket text; pago text; qty integer; pr numeric; co numeric; de numeric;
begin
 select * into lote from public.bodega_lotes where id=p_lote for update;
 if not found then raise exception 'Lote no válido'; end if;
 if lote.estado='PROCESADO' then return jsonb_build_object('lote_id',p_lote,'filas',lote.filas,'estado','PROCESADO'); end if;
 for fila in select payload from public.bodega_staging where lote_id=p_lote order by numero loop
  ticket:=trim(fila.payload->>'ticket'); f:=(fila.payload->>'fecha')::date;
  pago:=fila.payload->>'medio_pago'; qty:=(fila.payload->>'cantidad')::integer;
  pr:=(fila.payload->>'precio_unitario')::numeric; co:=(fila.payload->>'costo_unitario')::numeric;
  de:=(fila.payload->>'descuento')::numeric;
  if ticket is null or length(ticket) not between 1 and 100 or f is null or
   f>(now() at time zone 'America/Lima')::date or qty is null or qty<=0 or qty>100000 or
   pr is null or co is null or de is null or pr<0 or co<0 or de<0 or de>qty*pr or
   pr<>round(pr,2) or co<>round(co,2) or de<>round(de,2) then raise exception 'Lote no válido'; end if;
  select * into prod from public.bodega_productos where codigo=trim(fila.payload->>'codigo');
  if not found then raise exception 'Código desconocido'; end if;
  perform public.bodega_asegurar_fecha(f);
  select id into venta from public.bodega_ventas where ticket_externo=ticket;
  if found then
   if not exists(select 1 from public.bodega_ventas where id=venta and lote_id=p_lote and fecha=f and medio_pago=pago) then
    raise exception 'Ticket histórico ya existe o inconsistente'; end if;
  else
   insert into public.bodega_ventas(fecha,fecha_hora,medio_pago,origen,ticket_externo,lote_id,usuario_uid)
   values(f,(f+time '12:00') at time zone 'America/Lima',pago,'HISTORICO',ticket,p_lote,p_usuario) returning id into venta;
  end if;
  insert into public.bodega_detalle_venta(venta_id,producto_id,cantidad,precio_unitario,costo_unitario,descuento)
  values(venta,prod.id,qty,pr,co,de);
 end loop;
 update public.bodega_ventas v set total=(select sum(ingreso) from public.bodega_detalle_venta d where d.venta_id=v.id)
 where lote_id=p_lote;
 update public.bodega_lotes set estado='PROCESADO',procesado_en=now() where id=p_lote;
 -- Historia analítica: NO se resta del stock actual ni se crean movimientos de hoy.
 return jsonb_build_object('lote_id',p_lote,'filas',lote.filas,'estado','PROCESADO');
end $$;

create or replace function public.bodega_anular_venta(p_operacion uuid,p_venta bigint,p_motivo text,p_usuario text)
returns jsonb language plpgsql set search_path=public,pg_temp as $$
declare op public.bodega_operaciones; v public.bodega_ventas; d record; payload jsonb; nuevo integer;
 v_resultado jsonb;
begin
 payload:=jsonb_build_object('venta',p_venta,'motivo',p_motivo);
 insert into public.bodega_operaciones(id,tipo,payload,usuario_uid)
 values(p_operacion,'ANULACION',payload,p_usuario) on conflict do nothing;
 select * into op from public.bodega_operaciones where id=p_operacion for update;
 if op.tipo<>'ANULACION' or op.payload<>payload or op.usuario_uid<>p_usuario then raise exception 'Operación reutilizada'; end if;
 if op.resultado is not null then return op.resultado; end if;
 if length(trim(coalesce(p_motivo,'')))<3 then raise exception 'Motivo requerido'; end if;
 select * into v from public.bodega_ventas where id=p_venta for update;
 if not found then raise exception 'Código desconocido'; end if;
 if v.estado='COMPLETADA' then
  if v.origen='POS' then
   perform id from public.bodega_productos where id in
    (select producto_id from public.bodega_detalle_venta where venta_id=p_venta) order by id for update;
   for d in select * from public.bodega_detalle_venta where venta_id=p_venta loop
    update public.bodega_productos set stock=stock+d.cantidad where id=d.producto_id returning stock into nuevo;
    insert into public.bodega_movimientos(producto_id,tipo,variacion,stock_resultante,costo_unitario,motivo,venta_id,usuario_uid)
    values(d.producto_id,'ANULACION',d.cantidad,nuevo,d.costo_unitario,p_motivo,p_venta,p_usuario);
   end loop;
  end if;
  update public.bodega_ventas set estado='ANULADA' where id=p_venta;
 end if;
 v_resultado:=jsonb_build_object('venta_id',p_venta,'estado','ANULADA');
 update public.bodega_operaciones set resultado=v_resultado where id=p_operacion;
 return v_resultado;
end $$;

create or replace function public.bodega_guardar_predicciones(p_filas jsonb,p_usuario text) returns jsonb
language plpgsql set search_path=public,pg_temp as $$
declare f jsonb;
begin
 if jsonb_typeof(p_filas)<>'array' or jsonb_array_length(p_filas) not between 1 and 1000 then raise exception 'Lote no válido'; end if;
 for f in select value from jsonb_array_elements(p_filas) loop
  insert into public.bodega_predicciones(producto_id,fecha,corte,unidades,metodo,wape_validacion,wape_baseline,usuario_uid)
  values((f->>'producto_id')::bigint,(f->>'fecha')::date,(f->>'corte')::date,(f->>'unidades')::numeric,
   f->>'metodo',(f->>'wape_validacion')::double precision,(f->>'wape_baseline')::double precision,p_usuario)
  on conflict(producto_id,fecha,corte) do update set unidades=excluded.unidades,metodo=excluded.metodo,
   wape_validacion=excluded.wape_validacion,wape_baseline=excluded.wape_baseline,usuario_uid=excluded.usuario_uid,creado_en=now();
 end loop;
 return jsonb_build_object('filas',jsonb_array_length(p_filas));
end $$;

create or replace function public.bodega_decidir_reposicion(p_id uuid,p_producto bigint,p_unidades integer,
 p_decision text,p_motivo text,p_contexto jsonb,p_usuario text) returns jsonb
language plpgsql set search_path=public,pg_temp as $$
declare r public.bodega_reposiciones;
begin
 insert into public.bodega_reposiciones(id,producto_id,unidades,decision,motivo,contexto,usuario_uid)
 values(p_id,p_producto,p_unidades,p_decision,p_motivo,p_contexto,p_usuario) on conflict(id) do nothing;
 select * into r from public.bodega_reposiciones where id=p_id;
 if r.producto_id<>p_producto or r.unidades<>p_unidades or r.decision<>p_decision or
 r.motivo<>p_motivo or r.contexto<>p_contexto or r.usuario_uid<>p_usuario then raise exception 'Operación reutilizada'; end if;
 return jsonb_build_object('id',r.id,'decision',r.decision);
end $$;

-- Grano del hecho: una línea por producto por ticket; dimensiones normalizadas.
create or replace view public.bodega_v_ventas with (security_invoker=true) as
select d.id as id_detalle,v.id as venta_id,v.fecha,v.fecha_hora,v.medio_pago,v.origen,
 p.id as producto_id,p.codigo,p.nombre,c.nombre as categoria,pr.nombre as proveedor,
 t.anio,t.mes,t.dia_semana,d.cantidad,d.precio_unitario,d.costo_unitario,d.descuento,
 d.ingreso,d.margen_bruto
from public.bodega_detalle_venta d join public.bodega_ventas v on v.id=d.venta_id
join public.bodega_productos p on p.id=d.producto_id
join public.bodega_categorias c on c.id=p.categoria_id
join public.bodega_proveedores pr on pr.id=p.proveedor_id
join public.bodega_tiempo t on t.fecha=v.fecha where v.estado='COMPLETADA';

-- Acceso privado: solo el servidor Streamlit tras verificar Firebase y el rol.
-- No se expone service_role al navegador; Firebase no se usa como JWT Supabase.
do $$ declare t text; r record;
begin
 foreach t in array array['bodega_categorias','bodega_proveedores','bodega_productos','bodega_tiempo',
 'bodega_lotes','bodega_staging','bodega_ventas','bodega_detalle_venta','bodega_movimientos',
 'bodega_operaciones','bodega_predicciones','bodega_eventos','bodega_reposiciones'] loop
  execute format('alter table public.%I enable row level security',t);
  execute format('revoke all on public.%I from anon, authenticated',t);
  execute format('grant all on public.%I to service_role',t);
 end loop;
 for r in select oid::regprocedure as sig from pg_proc where pronamespace='public'::regnamespace
  and proname like 'bodega\_%' escape '\' loop
  execute format('revoke all on function %s from public, anon, authenticated',r.sig);
  execute format('grant execute on function %s to service_role',r.sig);
 end loop;
 for r in select sequence_schema,sequence_name from information_schema.sequences
  where sequence_schema='public' and sequence_name like 'bodega\_%' escape '\' loop
  execute format('grant usage,select on sequence %I.%I to service_role',r.sequence_schema,r.sequence_name);
 end loop;
end $$;
revoke all on public.bodega_v_ventas from anon,authenticated;
grant select on public.bodega_v_ventas to service_role;
notify pgrst,'reload schema';
commit;
