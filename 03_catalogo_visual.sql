-- Ejecutar una vez después de 01_bodega_schema.sql.
-- Añade información visual a productos. No altera stock ni ventas existentes.
begin;
alter table public.bodega_productos
 add column if not exists descripcion text not null default '',
 add column if not exists marca text not null default '',
 add column if not exists presentacion text not null default '',
 add column if not exists imagen_url text not null default '';

create or replace function public.bodega_guardar_producto_catalogo(p_producto jsonb) returns jsonb
language plpgsql set search_path=public,pg_temp as $$
declare r jsonb; pid bigint; foto text;
begin
 foto:=trim(coalesce(p_producto->>'imagen_url',''));
 if length(coalesce(p_producto->>'descripcion',''))>1500 or
    length(coalesce(p_producto->>'marca',''))>80 or
    length(coalesce(p_producto->>'presentacion',''))>120 or
    length(foto)>2048 or (foto<>'' and foto !~ '^https://[^[:space:]]+$') then
  raise exception 'Información de producto inválida';
 end if;
 -- Se conserva la función operativa original; todo ocurre en la misma transacción.
 r:=public.bodega_guardar_producto(p_producto);
 pid:=(r->>'producto_id')::bigint;
 update public.bodega_productos set
  descripcion=trim(coalesce(p_producto->>'descripcion','')),
  marca=trim(coalesce(p_producto->>'marca','')),
  presentacion=trim(coalesce(p_producto->>'presentacion','')),
  imagen_url=foto where id=pid;
 return r||jsonb_build_object('catalogo_version',2);
end $$;

revoke all on function public.bodega_guardar_producto_catalogo(jsonb) from public,anon,authenticated;
grant execute on function public.bodega_guardar_producto_catalogo(jsonb) to service_role;
notify pgrst,'reload schema';
commit;
