-- OPCIONAL: solo entorno de demostración vacío. Productos y stock SINTÉTICOS.
-- No usar para el inventario real de la bodega. Historia: importar data/ventas_demo.csv.
begin;
DO $$
declare p jsonb; pid bigint; op uuid;
begin
for p in select value from jsonb_array_elements('[{"codigo": "7750001000011", "nombre": "Arroz extra 1 kg", "categoria": "Abarrotes", "proveedor": "Distribuidora Norte", "precio": 4.8, "costo": 3.6, "stock": 8, "stock_minimo": 8, "plazo_dias": 2, "activo": true}, {"codigo": "7750001000028", "nombre": "Azúcar rubia 1 kg", "categoria": "Abarrotes", "proveedor": "Distribuidora Norte", "precio": 4.2, "costo": 3.2, "stock": 32, "stock_minimo": 8, "plazo_dias": 2, "activo": true}, {"codigo": "7750001000035", "nombre": "Aceite vegetal 1 L", "categoria": "Abarrotes", "proveedor": "Distribuidora Norte", "precio": 9.5, "costo": 7.2, "stock": 0, "stock_minimo": 6, "plazo_dias": 3, "activo": true}, {"codigo": "7750001000042", "nombre": "Leche evaporada 400 g", "categoria": "Lácteos", "proveedor": "Lácteos Lima", "precio": 4.5, "costo": 3.3, "stock": 14, "stock_minimo": 10, "plazo_dias": 2, "activo": true}, {"codigo": "7750001000059", "nombre": "Yogur fresa 1 L", "categoria": "Lácteos", "proveedor": "Lácteos Lima", "precio": 7.5, "costo": 5.6, "stock": 6, "stock_minimo": 6, "plazo_dias": 1, "activo": true}, {"codigo": "7750001000066", "nombre": "Agua sin gas 625 ml", "categoria": "Bebidas", "proveedor": "Bebidas del Perú", "precio": 1.8, "costo": 1.1, "stock": 45, "stock_minimo": 12, "plazo_dias": 2, "activo": true}, {"codigo": "7750001000073", "nombre": "Gaseosa 1.5 L", "categoria": "Bebidas", "proveedor": "Bebidas del Perú", "precio": 7.0, "costo": 5.1, "stock": 18, "stock_minimo": 10, "plazo_dias": 2, "activo": true}, {"codigo": "7750001000080", "nombre": "Galletas vainilla", "categoria": "Snacks", "proveedor": "Distribuidora Norte", "precio": 1.5, "costo": 0.9, "stock": 52, "stock_minimo": 15, "plazo_dias": 3, "activo": true}, {"codigo": "7750001000097", "nombre": "Papas fritas 40 g", "categoria": "Snacks", "proveedor": "Distribuidora Norte", "precio": 2.5, "costo": 1.65, "stock": 7, "stock_minimo": 10, "plazo_dias": 3, "activo": true}, {"codigo": "7750001000103", "nombre": "Detergente 500 g", "categoria": "Limpieza", "proveedor": "Limpieza Hogar", "precio": 5.5, "costo": 4.1, "stock": 21, "stock_minimo": 5, "plazo_dias": 4, "activo": true}, {"codigo": "7750001000110", "nombre": "Jabón de tocador", "categoria": "Limpieza", "proveedor": "Limpieza Hogar", "precio": 3.2, "costo": 2.0, "stock": 30, "stock_minimo": 6, "plazo_dias": 4, "activo": true}, {"codigo": "7750001000127", "nombre": "Atún en conserva", "categoria": "Abarrotes", "proveedor": "Distribuidora Norte", "precio": 6.8, "costo": 5.2, "stock": 0, "stock_minimo": 5, "plazo_dias": 3, "activo": true}]'::jsonb) loop
 select id into pid from public.bodega_productos where codigo=p->>'codigo';
 if not found then
  pid:=(public.bodega_guardar_producto(p)->>'producto_id')::bigint;
  if (p->>'stock')::integer>0 then
   op:=md5('demo-stock:'||(p->>'codigo'))::uuid;
   perform public.bodega_registrar_movimiento(op,pid,'ENTRADA',(p->>'stock')::integer,(p->>'costo')::numeric,'Inventario sintético de demostración','DEMO');
  end if;
 end if;
end loop;
end $$;
commit;
