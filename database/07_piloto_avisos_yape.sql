-- Compatible con el protocolo del APK piloto entregado. Solo avisos, no pagos bancarios verificados.
begin;
create table if not exists public.bodega_pago_dispositivos (
 id uuid primary key,nombre text not null check(length(trim(nombre)) between 2 and 60),
 token_hash text not null check(token_hash ~ '^[a-f0-9]{64}$'),activo boolean not null default true,
 creado_por text not null,creado_en timestamptz not null default now(),ultimo_contacto timestamptz,
 ventana timestamptz not null default now(),peticiones integer not null default 0
);
create table if not exists public.bodega_pago_avisos (
 id bigint generated always as identity primary key,dispositivo_id uuid not null references public.bodega_pago_dispositivos(id),
 evento_hash text not null check(evento_hash ~ '^[a-f0-9]{64}$'),
 importe_centimos integer not null check(importe_centimos between 1 and 10000000),
 notificado_en timestamptz not null,recibido_en timestamptz not null default now(),
 paquete text not null check(paquete='com.bcp.innovacxion.yapeapp'),unique(dispositivo_id,evento_hash)
);
create index if not exists bodega_pago_avisos_fecha_idx on public.bodega_pago_avisos(notificado_en desc,id desc);
create or replace function public.bodega_vincular_receptor(p_id uuid,p_nombre text,p_token_hash text,p_usuario text)
returns jsonb language plpgsql security definer set search_path=public,pg_temp as $$
begin
 if p_id is null or length(trim(coalesce(p_nombre,''))) not between 2 and 60 or coalesce(p_token_hash,'') !~ '^[a-f0-9]{64}$'
 then raise exception 'Datos del receptor inválidos';end if;
 insert into bodega_pago_dispositivos(id,nombre,token_hash,creado_por) values(p_id,trim(p_nombre),p_token_hash,p_usuario);
 return jsonb_build_object('id',p_id);
end $$;
create or replace function public.bodega_revocar_receptor(p_id uuid,p_usuario text) returns jsonb language plpgsql
security definer set search_path=public,pg_temp as $$
begin update bodega_pago_dispositivos set activo=false where id=p_id;return jsonb_build_object('revocado',found);end $$;
create or replace function public.bodega_recibir_aviso(p_dispositivo uuid,p_token_hash text,p_evento jsonb)
returns jsonb language plpgsql security definer set search_path=public,pg_temp as $$
declare d bodega_pago_dispositivos;a bodega_pago_avisos;ts timestamptz;cents integer;h text;
begin
 select * into d from bodega_pago_dispositivos where id=p_dispositivo for update;
 if not found or not d.activo or p_token_hash is distinct from d.token_hash then raise exception 'Receptor no autorizado' using errcode='28000';end if;
 if now()-d.ventana>=interval '1 minute' then d.ventana=now();d.peticiones=0;end if;
 if d.peticiones>=120 then raise exception 'Límite de avisos';end if;
 update bodega_pago_dispositivos set ultimo_contacto=now(),ventana=d.ventana,peticiones=d.peticiones+1 where id=d.id;
 if p_evento is null or p_evento='null'::jsonb then return jsonb_build_object('ok',true);end if;
 if jsonb_typeof(p_evento)!='object' or p_evento->>'package' is distinct from 'com.bcp.innovacxion.yapeapp'
 or coalesce(p_evento->>'event_id','') !~ '^[a-f0-9]{64}$' or coalesce(p_evento->>'amount_cents','') !~ '^[0-9]{1,8}$' then raise exception 'Aviso inválido';end if;
 h=p_evento->>'event_id';cents=(p_evento->>'amount_cents')::integer;ts=(p_evento->>'notified_at')::timestamptz;
 if ts is null or cents not between 1 and 10000000 then raise exception 'Aviso inválido';end if;
 select * into a from bodega_pago_avisos where dispositivo_id=d.id and evento_hash=h;
 if found then
  if a.importe_centimos<>cents or a.notificado_en<>ts then raise exception 'Evento reutilizado';end if;
  return jsonb_build_object('ok',true,'duplicado',true);
 end if;
 if not isfinite(ts) or ts<now()-interval '24 hours' or ts<d.creado_en-interval '5 minutes' or ts>now()+interval '5 minutes' then raise exception 'Hora del aviso inválida';end if;
 insert into bodega_pago_avisos(dispositivo_id,evento_hash,importe_centimos,notificado_en,paquete)
 values(d.id,h,cents,ts,p_evento->>'package');return jsonb_build_object('ok',true,'duplicado',false);
end $$;
create or replace function public.bodega_consultar_avisos(p_usuario text) returns jsonb language sql stable
security definer set search_path=public,pg_temp as $$
 select jsonb_build_object('dispositivos',coalesce((select jsonb_agg(to_jsonb(t)) from
 (select id,nombre,activo,ultimo_contacto,creado_en from bodega_pago_dispositivos order by creado_en desc limit 20)t),'[]'::jsonb))
$$;
do $$declare t text;f record;begin
 foreach t in array array['bodega_pago_dispositivos','bodega_pago_avisos'] loop
 execute format('alter table public.%I enable row level security',t);
 execute format('revoke all on public.%I from public,anon,authenticated',t);execute format('grant all on public.%I to service_role',t);end loop;
 for f in select p.oid::regprocedure as sig from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname='public'
 and p.proname in ('bodega_vincular_receptor','bodega_revocar_receptor','bodega_recibir_aviso','bodega_consultar_avisos') loop
 execute format('revoke all on function %s from public,anon,authenticated',f.sig);execute format('grant execute on function %s to service_role',f.sig);end loop;
end $$;
grant usage,select on sequence public.bodega_pago_avisos_id_seq to service_role;
notify pgrst,'reload schema';
commit;
