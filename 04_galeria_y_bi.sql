-- Actualización aditiva. Requiere 01_bodega_schema.sql y 03_catalogo_visual.sql.
-- No borra ventas, stock, imágenes anteriores ni tablas del campus.
begin;
alter table public.bodega_productos add column if not exists imagenes_urls jsonb not null default '[]'::jsonb;
update public.bodega_productos set imagenes_urls=jsonb_build_array(imagen_url)
 where imagenes_urls='[]'::jsonb and trim(imagen_url)<>'';
alter table public.bodega_eventos add column if not exists sesion_id uuid,
 add column if not exists pagina text not null default '';
create index if not exists bodega_eventos_sesion_idx on public.bodega_eventos(sesion_id,fecha_hora);

create or replace function public.bodega_guardar_producto_galeria(p_producto jsonb) returns jsonb
language plpgsql set search_path=public,pg_temp as $$
declare urls jsonb; clean jsonb:='[]'::jsonb; item jsonb; url text; r jsonb;
begin
 urls:=p_producto->'imagenes_urls';
 if urls is null then
  urls:=case when trim(coalesce(p_producto->>'imagen_url',''))='' then '[]'::jsonb
             else jsonb_build_array(p_producto->>'imagen_url') end;
 end if;
 if jsonb_typeof(urls)<>'array' or jsonb_array_length(urls)>8 then
  raise exception 'Galería inválida: máximo ocho URL';
 end if;
 for item in select value from jsonb_array_elements(urls) loop
  if jsonb_typeof(item)<>'string' then raise exception 'URL de imagen inválida'; end if;
  url:=trim(item#>>'{}');
  if url='' then continue; end if;
  if length(url)>2048 or url !~ '^https://[^/@[:space:]]+([/?#][^[:space:]]*)?$' then
   raise exception 'URL de imagen inválida';
  end if;
  if not clean @> jsonb_build_array(url) then clean:=clean||jsonb_build_array(url); end if;
 end loop;
 r:=public.bodega_guardar_producto_catalogo(p_producto||jsonb_build_object('imagen_url',coalesce(clean->>0,'')));
 update public.bodega_productos set imagenes_urls=clean where id=(r->>'producto_id')::bigint;
 return r||jsonb_build_object('imagenes',jsonb_array_length(clean));
end $$;
revoke all on function public.bodega_guardar_producto_galeria(jsonb) from public,anon,authenticated;
grant execute on function public.bodega_guardar_producto_galeria(jsonb) to service_role;

-- Cubo relacional virtual: no duplica los hechos. Cada subtotal recalcula tickets.
create or replace view public.bodega_v_cubo_ventas with (security_invoker=true) as
with base as (
 select to_char(fecha,'YYYY-MM') as periodo_mes,categoria,medio_pago,
        cantidad,ingreso,margen_bruto,venta_id
 from public.bodega_v_ventas
), cubo as (
 select periodo_mes,categoria,medio_pago,
   grouping(periodo_mes,categoria,medio_pago) as mascara_agrupacion,
   sum(cantidad) as unidades,sum(ingreso) as ventas,sum(margen_bruto) as margen_bruto,
   count(distinct venta_id) as tickets,
   sum(ingreso)/nullif(count(distinct venta_id),0) as ticket_promedio,
   100*sum(margen_bruto)/nullif(sum(ingreso),0) as margen_porcentaje
 from base group by cube(periodo_mes,categoria,medio_pago)
)
select row_number() over(order by mascara_agrupacion,periodo_mes nulls first,categoria nulls first,medio_pago nulls first) as id,*
from cubo;
revoke all on public.bodega_v_cubo_ventas from public,anon,authenticated;
grant select on public.bodega_v_cubo_ventas to service_role;
notify pgrst,'reload schema';
commit;
