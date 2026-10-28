-- Actualización aditiva para una base operativa hasta 11/12/13. Ejecutar SOLO este archivo.
-- No carga datos de ejemplo, no elimina ventas ni modifica existencias al instalarse.
begin;
create table if not exists public.bodega_movil_config (
 id boolean primary key default true check(id), project_id text not null, api_key text not null,
 actualizado_en timestamptz not null default now()
);
create table if not exists public.bodega_movil_equipo (
 uid text primary key,email text not null,nombre text not null,
 rol text not null check(rol in ('administrador','cajero','analista')),activo boolean not null default true
);
create table if not exists public.bodega_carritos (
 usuario_uid text primary key,items jsonb not null default '[]',revision bigint not null default 0,
 estado text not null default 'ABIERTO' check(estado in ('ABIERTO','COBRANDO')),
 operacion uuid,actualizado_en timestamptz not null default now()
);
create table if not exists public.bodega_movil_comandos (
 id uuid primary key,usuario_uid text not null,payload jsonb not null,resultado jsonb,
 creado_en timestamptz not null default now()
);
create table if not exists public.bodega_producto_codigos (
 codigo text primary key check(length(codigo) between 1 and 512 and codigo !~ '[[:cntrl:]]'),
 producto_id bigint not null references public.bodega_productos(id),creado_por text not null,creado_en timestamptz not null default now()
);
alter table public.bodega_productos add column if not exists revision_movil bigint not null default 0;
create or replace function public.bodega_revision_producto() returns trigger language plpgsql set search_path=public,pg_temp as $$
begin
 if (to_jsonb(new)-'stock'-'revision_movil') is distinct from (to_jsonb(old)-'stock'-'revision_movil') then new.revision_movil=old.revision_movil+1;else new.revision_movil=old.revision_movil;end if;return new;
end $$;
drop trigger if exists bodega_revision_ficha on public.bodega_productos;
create trigger bodega_revision_ficha before update on public.bodega_productos for each row execute function public.bodega_revision_producto();
create sequence if not exists public.bodega_catalogo_revision_seq;
create or replace function public.bodega_cambio_catalogo() returns trigger language plpgsql security definer set search_path=public,pg_temp as $$
begin perform nextval('public.bodega_catalogo_revision_seq');return null;end $$;
drop trigger if exists bodega_catalogo_revision on public.bodega_productos;
create trigger bodega_catalogo_revision after insert or update or delete on public.bodega_productos for each statement execute function public.bodega_cambio_catalogo();
create or replace function public.bodega_revision() returns bigint language sql security definer set search_path=public,pg_temp as $$
 select case when is_called then last_value else 0 end from bodega_catalogo_revision_seq
$$;
create or replace function public.bodega_activar_movil(p_project text,p_api_key text,p_equipo jsonb,p_usuario text) returns jsonb
language plpgsql security definer set search_path=public,pg_temp as $$
declare x jsonb;
begin
 if p_project is null or p_project !~ '^[a-z0-9-]{3,100}$' or p_api_key is null or length(p_api_key) not between 20 and 100
 or jsonb_typeof(p_equipo) is distinct from 'array' or jsonb_array_length(p_equipo) not between 1 and 1000 then raise exception 'Configuración móvil inválida';end if;
 if not exists(select 1 from jsonb_array_elements(p_equipo)e where e->>'uid'=p_usuario and e->>'rol'='administrador') then
 raise exception 'El administrador debe estar incluido en el equipo';end if;
 insert into bodega_movil_config(id,project_id,api_key) values(true,p_project,p_api_key)
 on conflict(id) do update set project_id=excluded.project_id,api_key=excluded.api_key,actualizado_en=now();
 update bodega_movil_equipo set activo=false where activo is true;
 for x in select * from jsonb_array_elements(p_equipo) loop
  if length(coalesce(x->>'uid','')) not between 1 and 128 or position('@' in coalesce(x->>'email',''))<2
  or coalesce(x->>'rol','') not in ('administrador','cajero','analista') or length(coalesce(x->>'nombre',''))>120 then raise exception 'Equipo móvil inválido';end if;
  insert into bodega_movil_equipo(uid,email,nombre,rol) values(x->>'uid',lower(trim(x->>'email')),coalesce(nullif(trim(x->>'nombre'),''),'Nombre pendiente'),x->>'rol')
  on conflict(uid) do update set email=excluded.email,nombre=excluded.nombre,rol=excluded.rol,activo=true;
 end loop;
 return jsonb_build_object('ok',true,'cuentas',jsonb_array_length(p_equipo));
end $$;
create or replace function public.bodega_config_movil() returns jsonb language sql stable security definer set search_path=public,pg_temp as $$
 select jsonb_build_object('project_id',project_id,'api_key',api_key,'version',14) from bodega_movil_config where id
$$;
create or replace function public.bodega_codigo_producto(p_codigo text) returns bigint language plpgsql stable security definer set search_path=public,pg_temp as $$
declare ids bigint[];
begin
 select array_agg(distinct x.id) into ids from (select id from bodega_productos where codigo=p_codigo union select producto_id from bodega_producto_codigos where codigo=p_codigo)x;
 if cardinality(ids)>1 then raise exception 'Código asociado a varios productos';end if;return ids[1];
end $$;
create or replace function public.bodega_carrito_consultar(p_usuario text) returns jsonb language plpgsql security definer set search_path=public,pg_temp as $$
declare c bodega_carritos;v bodega_operaciones;
begin
 if length(coalesce(p_usuario,'')) not between 1 and 128 then raise exception 'Usuario inválido';end if;
 insert into bodega_carritos(usuario_uid) values(p_usuario) on conflict do nothing;
 select * into c from bodega_carritos where usuario_uid=p_usuario for update;
 -- Recupera una respuesta perdida de una venta ya confirmada, sin tocar un carrito posterior.
 if c.estado='COBRANDO' then
  select * into v from bodega_operaciones where id=c.operacion and usuario_uid=p_usuario and tipo='VENTA' and resultado is not null;
  if found then update bodega_carritos set items='[]',estado='ABIERTO',operacion=null,revision=revision+1,actualizado_en=now()
   where usuario_uid=p_usuario returning * into c;end if;
 end if;
 return to_jsonb(c)-'usuario_uid'||jsonb_build_object('catalogo_revision',bodega_revision());
end $$;
create or replace function public.bodega_carrito_comando(p_id uuid,p_accion text,p_datos jsonb,p_revision bigint,p_usuario text) returns jsonb
language plpgsql security definer set search_path=public,pg_temp as $$
declare c bodega_carritos;v_request jsonb;v_saved bodega_movil_comandos;v_items jsonb;v_pid bigint;v_qty integer;v_disc numeric;v_count integer;v_total numeric;r jsonb;
begin
 if p_id is null or jsonb_typeof(p_datos) is distinct from 'object' or p_accion not in ('GUARDAR','AGREGAR','CANTIDAD','QUITAR','VACIAR') then raise exception 'Cambio de carrito inválido';end if;
 v_request=jsonb_build_object('accion',p_accion,'datos',p_datos,'revision',p_revision);
 insert into bodega_movil_comandos(id,usuario_uid,payload) values(p_id,p_usuario,v_request) on conflict do nothing;
 select * into v_saved from bodega_movil_comandos where id=p_id for update;
 if v_saved.usuario_uid<>p_usuario or v_saved.payload<>v_request then raise exception 'Operación reutilizada con otros datos';end if;
 if v_saved.resultado is not null then return v_saved.resultado;end if;
 perform bodega_carrito_consultar(p_usuario);
 select * into c from bodega_carritos where usuario_uid=p_usuario for update;
 if c.estado<>'ABIERTO' then raise exception 'El carrito está en proceso de cobro';end if;
 if p_revision is distinct from c.revision then raise exception using errcode='40001',message='El carrito cambió en otro dispositivo';end if;
 v_items=c.items;
 if p_accion='GUARDAR' then v_items=p_datos->'items';
 elsif p_accion='VACIAR' then v_items='[]';
 else
  v_pid=(p_datos->>'producto_id')::bigint;
  v_qty=coalesce((p_datos->>'cantidad')::integer,1);
  if (p_accion='AGREGAR' and v_qty not between 1 and 1000000) or (p_accion='CANTIDAD' and v_qty<0) then raise exception 'Cantidad inválida';end if;
  if p_accion='AGREGAR' then v_qty=v_qty+coalesce((select (x->>'cantidad')::integer from jsonb_array_elements(v_items)x where (x->>'producto_id')::bigint=v_pid),0);end if;
  v_disc=coalesce((select (x->>'descuento')::numeric from jsonb_array_elements(v_items)x where (x->>'producto_id')::bigint=v_pid),0);
  select coalesce(jsonb_agg(x),'[]'::jsonb) into v_items from jsonb_array_elements(v_items)x where (x->>'producto_id')::bigint<>v_pid;
  if p_accion<>'QUITAR' and v_qty>0 then v_items=v_items||jsonb_build_array(jsonb_build_object('producto_id',v_pid,'cantidad',v_qty,'descuento',v_disc));end if;
 end if;
 if jsonb_typeof(v_items) is distinct from 'array' or jsonb_array_length(v_items)>100 then raise exception 'Carrito inválido';end if;
 if jsonb_array_length(v_items)>0 then
  if exists(select 1 from jsonb_array_elements(v_items)x where coalesce(x->>'cantidad','') !~ '^[1-9][0-9]{0,6}$'
   or coalesce(x->>'producto_id','') !~ '^[1-9][0-9]{0,17}$' or coalesce(x->>'descuento','') !~ '^[0-9]+(\.[0-9]{1,2})?$') then raise exception 'Cantidad inválida';end if;
  select count(*),sum((x->>'cantidad')::integer*p.precio-(x->>'descuento')::numeric) into v_count,v_total
  from jsonb_array_elements(v_items)x join bodega_productos p on p.id=(x->>'producto_id')::bigint
  where p.activo and (x->>'cantidad')::integer<=p.stock and (x->>'descuento')::numeric between 0 and (x->>'cantidad')::integer*p.precio;
  if v_count<>jsonb_array_length(v_items) or v_count<>(select count(distinct x->>'producto_id') from jsonb_array_elements(v_items)x) then raise exception 'Stock insuficiente o producto inactivo';end if;
 end if;
 update bodega_carritos set items=v_items,revision=revision+1,actualizado_en=now() where usuario_uid=p_usuario;
 r=bodega_carrito_consultar(p_usuario);
 update bodega_movil_comandos set resultado=r where id=p_id;return r;
end $$;
create or replace function public.bodega_carrito_bloquear(p_id uuid,p_revision bigint,p_usuario text) returns jsonb language plpgsql security definer set search_path=public,pg_temp as $$
declare c bodega_carritos;
begin
 if p_id is null then raise exception 'Operación inválida';end if;
 if exists(select 1 from bodega_operaciones where id=p_id and usuario_uid=p_usuario and tipo='VENTA' and resultado is not null) then return jsonb_build_object('estado','TERMINADO');end if;
 perform bodega_carrito_consultar(p_usuario);select * into c from bodega_carritos where usuario_uid=p_usuario for update;
 if c.estado='COBRANDO' and c.operacion=p_id then return to_jsonb(c)-'usuario_uid';end if;
 if c.estado<>'ABIERTO' then raise exception 'El carrito está en proceso de cobro';end if;
 if c.revision is distinct from p_revision then raise exception using errcode='40001',message='El carrito cambió en otro dispositivo';end if;
 if jsonb_array_length(c.items)=0 then raise exception 'El carrito está vacío';end if;
 update bodega_carritos set estado='COBRANDO',operacion=p_id,revision=revision+1,actualizado_en=now() where usuario_uid=p_usuario returning * into c;
 return to_jsonb(c)-'usuario_uid';
end $$;
create or replace function public.bodega_carrito_liberar(p_id uuid,p_cancelar boolean,p_usuario text) returns jsonb language plpgsql security definer set search_path=public,pg_temp as $$
declare c bodega_carritos;
begin
 select * into c from bodega_carritos where usuario_uid=p_usuario for update;
 if not found then return jsonb_build_object('ok',true);end if;
 if c.operacion is not distinct from p_id and c.estado='COBRANDO' then
  if not p_cancelar and not exists(select 1 from bodega_operaciones where id=p_id and usuario_uid=p_usuario and tipo='VENTA' and resultado is not null) then raise exception 'La venta todavía no está confirmada';end if;
  if p_cancelar and exists(select 1 from bodega_cobros where id=p_id and usuario_uid=p_usuario and estado not in ('CANCELADO','VENCIDO','REGISTRADO')) then raise exception 'Resuelve primero el cobro abierto';end if;
  update bodega_carritos set items=case when exists(select 1 from bodega_operaciones where id=p_id and usuario_uid=p_usuario and tipo='VENTA' and resultado is not null) then '[]'::jsonb else items end,estado='ABIERTO',operacion=null,revision=revision+1,actualizado_en=now() where usuario_uid=p_usuario;
 end if;
 return jsonb_build_object('ok',true);
end $$;
create or replace function public.bodega_guardar_producto_revision(p_producto jsonb,p_revision bigint,p_usuario text) returns jsonb
language plpgsql security definer set search_path=public,pg_temp as $$
declare v_id bigint=(p_producto->>'id')::bigint;v_actual bigint;r jsonb;
begin
 if v_id is not null then
  select revision_movil into v_actual from bodega_productos where id=v_id for update;
  if not found then raise exception 'Código desconocido';end if;
  if v_actual is distinct from p_revision then raise exception using errcode='40001',message='El producto cambió en otro dispositivo. Recarga su ficha';end if;
 end if;
 if bodega_codigo_producto(trim(p_producto->>'codigo')) is not null and bodega_codigo_producto(trim(p_producto->>'codigo')) is distinct from v_id then raise exception 'Código asociado a otro producto';end if;
 r=bodega_guardar_producto_galeria(p_producto);
 insert into bodega_eventos(usuario_uid,evento,detalle) values(p_usuario,'producto_guardado',r->>'producto_id');return r;
end $$;
create or replace function public.bodega_movil_api(p_usuario text,p_email text,p_accion text,p_datos jsonb) returns jsonb
language plpgsql security definer set search_path=public,pg_temp as $$
declare u bodega_movil_equipo;v_pid bigint;v_page integer;v_q text;v_count bigint;v_rows jsonb;r jsonb;v_command bodega_movil_comandos;v_id uuid;v_revision bigint;v_alias text;
begin
 select * into u from bodega_movil_equipo where uid=p_usuario and email=lower(p_email) and activo;
 if not found then raise exception using errcode='42501',message='Tu cuenta no tiene acceso móvil. Actualiza el equipo desde la web';end if;
 if jsonb_typeof(p_datos) is distinct from 'object' then raise exception 'Datos inválidos';end if;
 if p_accion='perfil' then return jsonb_build_object('uid',u.uid,'nombre',u.nombre,'rol',u.rol,'email',u.email);end if;
 if p_accion='catalogo' then
  v_page=coalesce((p_datos->>'pagina')::integer,0);v_q=lower(trim(coalesce(p_datos->>'busqueda','')));
  if v_page not between 0 and 10000 or length(v_q)>120 then raise exception 'Búsqueda inválida';end if;
  with filtered as(select p.*,c.nombre categoria,s.nombre proveedor from bodega_productos p join bodega_categorias c on c.id=p.categoria_id join bodega_proveedores s on s.id=p.proveedor_id
   where (u.rol='administrador' or p.activo) and (v_q='' or strpos(lower(p.nombre||' '||p.codigo||' '||c.nombre),v_q)>0)),
  paged as(select * from filtered order by nombre,id limit 40 offset v_page*40)
  select (select count(*) from filtered),coalesce(jsonb_agg(case when u.rol='administrador' then to_jsonb(paged) else to_jsonb(paged)-'costo' end order by nombre,id),'[]'::jsonb) into v_count,v_rows from paged;
  return jsonb_build_object('productos',v_rows,'total',v_count,'pagina',v_page,'catalogo_revision',bodega_revision());
 end if;
 if p_accion='producto' then
  v_pid=coalesce((p_datos->>'id')::bigint,bodega_codigo_producto(trim(p_datos->>'codigo')));
  select to_jsonb(p)||jsonb_build_object('categoria',c.nombre,'proveedor',s.nombre) into r from bodega_productos p join bodega_categorias c on c.id=p.categoria_id join bodega_proveedores s on s.id=p.proveedor_id where p.id=v_pid;
  if r is null then raise exception 'Código no registrado en inventario';end if;
  if u.rol<>'administrador' then r=r-'costo';end if;return r;
 end if;
 if u.rol not in ('administrador','cajero') then raise exception using errcode='42501',message='Tu rol no permite modificar la tienda';end if;
 if p_accion='carrito' then
  r=bodega_carrito_consultar(p_usuario);
  select coalesce(jsonb_agg(jsonb_build_object('producto_id',p.id,'codigo',p.codigo,'nombre',p.nombre,'precio',p.precio,'stock',p.stock,'activo',p.activo,
   'cantidad',(x->>'cantidad')::integer,'descuento',(x->>'descuento')::numeric,'imagen_url',p.imagen_url)),'[]'::jsonb) into v_rows
   from jsonb_array_elements(r->'items')x join bodega_productos p on p.id=(x->>'producto_id')::bigint;
  return r||jsonb_build_object('lineas',v_rows);
 end if;
 if p_accion='carrito_cambiar' then return bodega_carrito_comando((p_datos->>'operacion')::uuid,p_datos->>'accion',p_datos->'datos',(p_datos->>'revision')::bigint,p_usuario);end if;
 if u.rol<>'administrador' then raise exception using errcode='42501',message='Solo administración puede editar inventario';end if;
 if p_accion not in ('guardar_producto','movimiento','asociar_codigo') then raise exception 'Acción móvil inválida';end if;
 v_id=(p_datos->>'operacion')::uuid;
 if v_id is null then raise exception 'Operación requerida';end if;
 insert into bodega_movil_comandos(id,usuario_uid,payload) values(v_id,p_usuario,jsonb_build_object('accion',p_accion,'datos',p_datos)) on conflict do nothing;
 select * into v_command from bodega_movil_comandos where id=v_id for update;
 if v_command.usuario_uid<>p_usuario or v_command.payload<>jsonb_build_object('accion',p_accion,'datos',p_datos) then raise exception 'Operación reutilizada con otros datos';end if;
 if v_command.resultado is not null then return v_command.resultado;end if;
 if p_accion='guardar_producto' then
  v_pid=(p_datos->'producto'->>'id')::bigint;
  if v_pid is not null then
   select revision_movil into v_revision from bodega_productos where id=v_pid for update;
   if not found then raise exception 'Código desconocido';end if;
   if v_revision is distinct from (p_datos->>'revision_producto')::bigint then raise exception using errcode='40001',message='El producto cambió en otro dispositivo. Recarga su ficha';end if;
  end if;
  if bodega_codigo_producto(trim(p_datos->'producto'->>'codigo')) is not null and bodega_codigo_producto(trim(p_datos->'producto'->>'codigo')) is distinct from v_pid then raise exception 'Código asociado a otro producto';end if;
  r=bodega_guardar_producto_revision(p_datos->'producto',(p_datos->>'revision_producto')::bigint,p_usuario);
  v_alias=trim(coalesce(p_datos->>'codigo_alternativo',''));
  if v_alias<>'' then
   if length(v_alias)>512 or v_alias ~ '[[:cntrl:]]' then raise exception 'Código inválido';end if;
   perform pg_advisory_xact_lock(hashtext(v_alias));
   if bodega_codigo_producto(v_alias) is not null and bodega_codigo_producto(v_alias)<>(r->>'producto_id')::bigint then raise exception 'Código asociado a otro producto';end if;
   insert into bodega_producto_codigos(codigo,producto_id,creado_por) values(v_alias,(r->>'producto_id')::bigint,p_usuario) on conflict do nothing;
  end if;
  insert into bodega_eventos(usuario_uid,evento,detalle) values(p_usuario,'producto_guardado_movil',r->>'producto_id');
 elsif p_accion='movimiento' then
  r=bodega_registrar_movimiento(v_id,(p_datos->>'producto_id')::bigint,p_datos->>'tipo',(p_datos->>'cantidad')::integer,(p_datos->>'costo')::numeric,p_datos->>'motivo',p_usuario);
 else
  v_pid=(p_datos->>'producto_id')::bigint;
  if length(trim(p_datos->>'codigo')) not between 1 and 512 or p_datos->>'codigo' ~ '[[:cntrl:]]' then raise exception 'Código inválido';end if;
  perform pg_advisory_xact_lock(hashtext(p_datos->>'codigo'));
  if bodega_codigo_producto(p_datos->>'codigo') is not null and bodega_codigo_producto(p_datos->>'codigo')<>v_pid then raise exception 'Código asociado a otro producto';end if;
  insert into bodega_producto_codigos(codigo,producto_id,creado_por) values(trim(p_datos->>'codigo'),v_pid,p_usuario) on conflict do nothing;
  perform nextval('public.bodega_catalogo_revision_seq');r=jsonb_build_object('producto_id',v_pid);
 end if;
 update bodega_movil_comandos set resultado=r where id=v_id;return r;
end $$;
-- Todas las identidades y roles se comprueban en el servidor. Nada es público salvo la configuración Firebase pública que filtra el endpoint.
alter table bodega_movil_config enable row level security;alter table bodega_movil_equipo enable row level security;
alter table bodega_carritos enable row level security;alter table bodega_movil_comandos enable row level security;
alter table bodega_producto_codigos enable row level security;
revoke all on bodega_movil_config,bodega_movil_equipo,bodega_carritos,bodega_movil_comandos,bodega_producto_codigos from public,anon,authenticated;
grant all on bodega_movil_config,bodega_movil_equipo,bodega_carritos,bodega_movil_comandos,bodega_producto_codigos to service_role;
revoke all on sequence bodega_catalogo_revision_seq from public,anon,authenticated;grant usage,select on sequence bodega_catalogo_revision_seq to service_role;
revoke all on function bodega_cambio_catalogo(),bodega_revision(),bodega_config_movil(),bodega_activar_movil(text,text,jsonb,text),bodega_codigo_producto(text),
 bodega_carrito_consultar(text),bodega_carrito_comando(uuid,text,jsonb,bigint,text),bodega_carrito_bloquear(uuid,bigint,text),bodega_carrito_liberar(uuid,boolean,text),bodega_movil_api(text,text,text,jsonb) from public,anon,authenticated;
grant execute on function bodega_cambio_catalogo(),bodega_revision(),bodega_config_movil(),bodega_activar_movil(text,text,jsonb,text),bodega_codigo_producto(text),
 bodega_carrito_consultar(text),bodega_carrito_comando(uuid,text,jsonb,bigint,text),bodega_carrito_bloquear(uuid,bigint,text),bodega_carrito_liberar(uuid,boolean,text),bodega_movil_api(text,text,text,jsonb) to service_role;
revoke all on function bodega_revision_producto() from public,anon,authenticated;grant execute on function bodega_revision_producto() to service_role;
alter table public.bodega_clientes alter column nombre drop not null;
alter table public.bodega_clientes drop constraint if exists bodega_clientes_nombre_check;
alter table public.bodega_clientes drop constraint if exists bodega_cliente_nombre_opcional_check;
alter table public.bodega_clientes add constraint bodega_cliente_nombre_opcional_check check(nombre is null or length(trim(nombre)) between 2 and 120);
create or replace function public.bodega_buscar_clientes(p_busqueda text,p_usuario text) returns jsonb language sql stable security definer set search_path=public,pg_temp as $$
 select coalesce(jsonb_agg(to_jsonb(x) order by prioridad,nombre nulls last,dni),'[]'::jsonb) from
 (select id,dni,nombre,case when dni=trim(p_busqueda) then 0 else 1 end prioridad from bodega_clientes
 where strpos(translate(lower(concat_ws(' ',dni,nombre)),'áéíóúüñ','aeiouun'),translate(lower(trim(coalesce(p_busqueda,''))),'áéíóúüñ','aeiouun'))>0
 order by prioridad,nombre nulls last,dni limit 75)x
$$;
create or replace function public.bodega_registrar_venta_caja(p_operacion uuid,p_items jsonb,p_pago text,p_usuario text,
 p_pago_confirmado boolean,p_total_confirmado numeric,p_cliente jsonb,p_referencia text,p_entidad text)
returns jsonb language plpgsql security definer set search_path=public,pg_temp as $$
declare r jsonb;v bodega_ventas;v_cli bigint;v_dni text;v_nombre text;v_ref text;v_entidad text;v_payload jsonb;
begin
 v_dni=trim(coalesce(p_cliente->>'dni',''));v_nombre=regexp_replace(trim(coalesce(p_cliente->>'nombre','')),'\s+',' ','g');
 v_ref=upper(trim(coalesce(p_referencia,'')));v_entidad=upper(trim(coalesce(p_entidad,'')));
 if p_pago='Efectivo' then v_ref='';v_entidad='';end if;
 v_payload=jsonb_build_object('dni',v_dni,'nombre',v_nombre,'referencia',v_ref,'entidad',v_entidad);
 select vta.* into v from bodega_ventas vta join bodega_operaciones op on op.id=p_operacion where op.tipo='VENTA' and vta.id=(op.resultado->>'venta_id')::bigint and op.usuario_uid=p_usuario;
 if found and v.caja_payload is not null then
  if v.caja_payload<>v_payload then raise exception 'Datos de caja cambiaron';end if;
  r=bodega_registrar_venta_pagada(p_operacion,p_items,p_pago,p_usuario,p_pago_confirmado,p_total_confirmado);
  return r||jsonb_build_object('orden',bodega_numero_orden(v.id));
 end if;
 if jsonb_typeof(p_cliente) is distinct from 'object' or v_dni !~ '^[0-9]{8}$' or (v_nombre<>'' and length(v_nombre) not between 2 and 120) then raise exception 'Datos del cliente inválidos';end if;
 if coalesce(p_pago,'') not in ('Efectivo','Yape','Transferencia') then raise exception 'Medio de pago inválido';end if;
 if p_pago<>'Efectivo' and (v_ref !~ '^[A-Z0-9._/-]{4,100}$' or length(v_entidad) not between 1 and 60) then raise exception 'Referencia de pago requerida';end if;
 r=bodega_registrar_venta_pagada(p_operacion,p_items,p_pago,p_usuario,p_pago_confirmado,p_total_confirmado);
 select * into v from bodega_ventas where id=(r->>'venta_id')::bigint for update;
 if v.caja_payload is not null then
  if v.caja_payload<>v_payload then raise exception 'Datos de caja cambiaron';end if;return r||jsonb_build_object('orden',bodega_numero_orden(v.id));
 end if;
 insert into bodega_clientes(dni,nombre) values(v_dni,nullif(v_nombre,'')) on conflict(dni)
 do update set nombre=coalesce(excluded.nombre,bodega_clientes.nombre),actualizado_en=now() returning id into v_cli;
 begin
 update bodega_ventas set cliente_id=v_cli,cliente_dni=v_dni,cliente_nombre=nullif(v_nombre,''),pago_referencia=nullif(v_ref,''),pago_entidad=nullif(v_entidad,''),pago_validacion='MANUAL_CAJA',caja_payload=v_payload where id=v.id;
 exception when unique_violation then raise exception 'Referencia de pago ya utilizada';end;
 insert into bodega_tickets(venta_id,datos) values(v.id,bodega_datos_ticket(v.id)) on conflict do nothing;
 return r||jsonb_build_object('orden',bodega_numero_orden(v.id));
end $$;
create or replace function public.bodega_confirmar_cobro_aviso(p_id uuid,p_usuario text) returns jsonb language plpgsql security definer set search_path=public,pg_temp as $$
declare c bodega_cobros;a bodega_pago_avisos;device uuid;active boolean;state jsonb;r jsonb;
begin
 select dispositivo_id into device from bodega_cobros where id=p_id and usuario_uid=p_usuario;
 if not found then raise exception 'Cobro no encontrado';end if;
 select activo into active from bodega_pago_dispositivos where id=device for update;
 select * into c from bodega_cobros where id=p_id and usuario_uid=p_usuario for update;
 if c.estado='REGISTRADO' then return jsonb_build_object('estado','REGISTRADO','venta_id',c.venta_id,'total',c.importe_centimos/100.0,'orden',bodega_numero_orden(c.venta_id));end if;
 if not active then raise exception 'Receptor no autorizado';end if;
 if c.estado in ('CANCELADO','VENCIDO') then raise exception 'El aviso requiere conciliación';end if;
 state=bodega_estado_cobro(p_id,p_usuario);
 if state->>'estado'<>'DETECTADO' then raise exception 'La orden no tiene un aviso único';end if;
 select * into c from bodega_cobros where id=p_id;
 select * into a from bodega_pago_avisos where id=c.aviso_id for update;
 if a.paquete<>'com.bcp.innovacxion.yapeapp' or a.dispositivo_id<>c.dispositivo_id or a.importe_centimos<>c.importe_centimos
 or a.notificado_en<c.creado_en or a.notificado_en>c.vence_en or a.recibido_en<c.creado_en
 or a.recibido_en-a.notificado_en not between interval '-5 seconds' and interval '30 seconds' then raise exception 'El aviso requiere conciliación';end if;
 if now()<a.recibido_en+interval '5 seconds' then return jsonb_build_object('estado','OBSERVANDO');end if;
 r=bodega_registrar_venta_caja(c.id,c.items,'Yape',p_usuario,true,c.importe_centimos/100.0,c.cliente,'AVISO-YAPE-'||a.id::text,'YAPE DEL NEGOCIO');
 update bodega_ventas set pago_validacion='AVISO_DISPOSITIVO' where id=(r->>'venta_id')::bigint;
 update bodega_tickets set datos=datos||jsonb_build_object('pago_validacion','AVISO_DISPOSITIVO','aviso_id',a.id,'dispositivo_id',c.dispositivo_id,'cobro_id',c.id) where venta_id=(r->>'venta_id')::bigint;
 update bodega_cobros set estado='REGISTRADO',venta_id=(r->>'venta_id')::bigint where id=c.id;
 return r||jsonb_build_object('estado','REGISTRADO');
end $$;
revoke all on function bodega_buscar_clientes(text,text),bodega_registrar_venta_caja(uuid,jsonb,text,text,boolean,numeric,jsonb,text,text),bodega_confirmar_cobro_aviso(uuid,text) from public,anon,authenticated;
grant execute on function bodega_buscar_clientes(text,text),bodega_registrar_venta_caja(uuid,jsonb,text,text,boolean,numeric,jsonb,text,text),bodega_confirmar_cobro_aviso(uuid,text) to service_role;

revoke all on function bodega_guardar_producto_revision(jsonb,bigint,text) from public,anon,authenticated;grant execute on function bodega_guardar_producto_revision(jsonb,bigint,text) to service_role;
notify pgrst,'reload schema';
commit;
