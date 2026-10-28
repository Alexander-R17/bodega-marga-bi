-- Corrección 14.1: activación compatible con la protección safeupdate de Supabase.
-- Ejecutar DESPUÉS del SQL 14, en SQL Editor. No requiere SQL 13.
-- Solo reemplaza la función de activación. No carga productos ni modifica stock o ventas.
-- Conserva RLS y los permisos privados; no desactiva safeupdate.
begin;
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
revoke all on function public.bodega_activar_movil(text,text,jsonb,text) from public,anon,authenticated;
grant execute on function public.bodega_activar_movil(text,text,jsonb,text) to service_role;
notify pgrst,'reload schema';
commit;
