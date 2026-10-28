// Base PostgreSQL WASM aislada: nunca accede a Supabase ni necesita credenciales.
import {PGlite} from '@electric-sql/pglite';
import {readFileSync,writeFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {randomUUID,createHash} from 'node:crypto';
import assert from 'node:assert/strict';
const root=fileURLToPath(new URL('../',import.meta.url));
const db=new PGlite();const checks=[];
const scalar=async(q,p=[])=>Object.values((await db.query(q,p)).rows[0])[0];
const pass=message=>{checks.push(message);console.log('PASS '+message);};
const items=id=>JSON.stringify([{producto_id:id,cantidad:1,descuento:0}]);
const customer=JSON.stringify({dni:'12345678',nombre:'Cliente Prueba'});
const hash=createHash('sha256').update('a'.repeat(64)).digest('hex');
async function receiver(){const id=randomUUID();await scalar("select bodega_vincular_receptor($1,'Prueba local',$2,'admin')",[id,hash]);return id;}
async function order(device){const id=randomUUID();await scalar("select bodega_abrir_cobro($1,$2,$3,$4,4.2,'cashier')",[id,device,items(2),customer]);return id;}
async function send(device){const event={event_id:randomUUID().replaceAll('-','')+'a'.repeat(32),package:'com.bcp.innovacxion.yapeapp',amount_cents:420,notified_at:new Date().toISOString()};await scalar('select bodega_recibir_aviso($1,$2,$3)',[device,hash,JSON.stringify(event)]);return scalar('select id from bodega_pago_avisos where evento_hash=$1',[event.event_id]);}
const state=id=>scalar("select bodega_estado_cobro($1,'cashier')",[id]);
const recover=(id,reviewed=true,actor='cashier')=>scalar('select bodega_conciliar_cobro_recibido($1,$2,$3)',[id,reviewed,actor]);
try{
 await db.exec('create role anon;create role authenticated;create role service_role bypassrls;');
 for(const f of ['01_bodega_schema.sql','03_catalogo_visual.sql','04_galeria_y_bi.sql','05_confirmacion_pago.sql','06_clientes_historial_ticket.sql','07_piloto_avisos_yape.sql','08_fiado.sql','09_espera_cobros.sql','11_correccion_clientes_y_conciliacion.sql'])await db.exec(readFileSync(root+'database/'+f,'utf8'));
 await db.exec(readFileSync(root+'database/02_catalogo_demo_OPCIONAL.sql','utf8'));
 await db.exec('update bodega_productos set precio=1.8,stock=20 where id=1;update bodega_productos set precio=4.2,stock=20 where id=2;');
 const paid=await scalar("select bodega_registrar_venta_caja($1,$2,'Yape','cashier',true,1.8,$3,'REC-001','YAPE')",[randomUUID(),items(1),customer]);
 assert.equal(Number(paid.total),1.8);assert.equal(await scalar('select count(*) from bodega_clientes'),1);
 pass('venta identificada de S/1.80 sin conflicto de variable DNI');
 const second=await scalar("select bodega_registrar_venta_caja($1,$2,'Yape','cashier',true,4.2,$3,'REC-002','YAPE')",[randomUUID(),items(2),customer]);
 assert.equal(Number(second.total),4.2);assert.equal(await scalar('select count(*) from bodega_clientes'),1);
 assert.equal(await scalar('select cliente_dni from bodega_ventas where id=$1',[second.venta_id]),'12345678');
 pass('segunda venta de S/4.20 reutiliza cliente sin duplicarlo');
 await assert.rejects(()=>scalar("select bodega_registrar_venta_caja($1,$2,'Yape','cashier',true,4.2,$3,'REC-003','YAPE')",[randomUUID(),items(2),JSON.stringify({dni:'Alexander',nombre:'Cliente Prueba'})]),/cliente inválidos/);
 pass('se mantiene validación del DNI del servidor');
 const device=await receiver(),op=await order(device),notice=await send(device);assert.equal((await state(op)).estado,'DETECTADO');
 // Simular paso del reloj manteniendo la evidencia dentro de la ventana original.
 await db.query("update bodega_cobros set creado_en=now()-interval '130 seconds',vence_en=now()-interval '10 seconds' where id=$1",[op]);
 await db.query("update bodega_pago_avisos set notificado_en=now()-interval '20 seconds',recibido_en=now()-interval '20 seconds' where id=$1",[notice]);
 assert.equal((await state(op)).estado,'DETECTADO');pass('aviso asociado permanece visible después del plazo');
 await db.query("update bodega_cobros set estado='VENCIDO' where id=$1",[op]);
 assert.equal((await scalar("select bodega_cobros_por_conciliar('cashier')"))[0].id,op);
 assert.deepEqual(await scalar("select bodega_cobros_por_conciliar('otro')"),[]);
 await assert.rejects(()=>recover(op,false),/Revisa el movimiento/);await assert.rejects(()=>recover(op,true,'otro'),/no encontrado/);
 pass('recuperación exige revisión y el usuario original; no expone otras cuentas');
 const stock=await scalar('select stock from bodega_productos where id=2'),count=await scalar('select count(*) from bodega_ventas');
 const recovered=await recover(op);assert.equal(Number(recovered.total),4.2);assert.deepEqual(await recover(op),recovered);
 assert.equal(await scalar('select count(*) from bodega_ventas'),count+1);assert.equal(await scalar('select stock from bodega_productos where id=2'),stock-1);
 assert.equal(await scalar('select aviso_id from bodega_cobros where id=$1',[op]),notice);
 const ticket=await scalar("select bodega_ticket_venta($1,'cashier')",[recovered.venta_id]);
 assert.equal(ticket.conciliacion_manual,true);assert.equal(ticket.aviso_id,notice);assert.equal(ticket.cobro_id,op);
 pass('recupera la orden vencida con su aviso original una vez; stock y ticket auditados');
 const unreceived=await order(await receiver());await db.query("update bodega_cobros set estado='VENCIDO' where id=$1",[unreceived]);
 await assert.rejects(()=>recover(unreceived),/no tiene un aviso/);pass('una orden sin aviso no se puede recuperar como pagada');
 const devStock=await receiver(),opStock=await order(devStock);await send(devStock);await state(opStock);
 await db.exec('update bodega_productos set stock=0 where id=2');
 const countStock=await scalar('select count(*) from bodega_ventas');await assert.rejects(()=>recover(opStock),/Stock insuficiente/);
 assert.equal(await scalar('select count(*) from bodega_ventas'),countStock);assert.equal(await scalar('select venta_id from bodega_cobros where id=$1',[opStock]),null);
 await db.exec('update bodega_productos set stock=20 where id=2');pass('sin stock no crea venta parcial ni pierde el aviso');
 const devAmb=await receiver(),opAmb=await order(devAmb);await send(devAmb);await state(opAmb);await send(devAmb);
 await assert.rejects(()=>recover(opAmb),/varios avisos/);pass('varios avisos del mismo importe impiden recuperar automáticamente');
 const devOld=await receiver(),opOld=await order(devOld),noticeOld=await send(devOld);await state(opOld);
 await db.query("update bodega_pago_avisos set notificado_en=now()-interval '5 minutes' where id=$1",[noticeOld]);
 await assert.rejects(()=>recover(opOld),/condiciones de la orden/);pass('rechaza aviso anterior a la orden y no relaja la ventana original');
 await scalar("select bodega_revocar_receptor($1,'admin')",[devStock]);await assert.rejects(()=>recover(opStock),/Receptor no autorizado/);
 pass('un receptor revocado no permite recuperar ventas nuevas');
 for(const role of ['anon','authenticated']){
  await db.exec('set role '+role);await assert.rejects(()=>scalar("select bodega_cobros_por_conciliar('cashier')"));await assert.rejects(()=>recover(op));await db.exec('reset role');
 }pass('funciones privadas: anon y authenticated no tienen acceso');
 await db.exec('set role service_role');assert.equal((await scalar("select bodega_cobros_por_conciliar('cashier')")).length>0,true);await db.exec('reset role');
 const currentSales=await scalar('select count(*) from bodega_ventas');await db.exec(readFileSync(root+'database/11_correccion_clientes_y_conciliacion.sql','utf8'));
 assert.equal(await scalar('select count(*) from bodega_ventas'),currentSales);pass('SQL 11 es repetible y no ejecuta ventas al instalarse');
 writeFileSync(root+'docs/17_VERIFICACION_SQL.json',JSON.stringify({checks,entorno:'PGlite local aislado',produccion_modificada:false,causa_reproducida_antes:'42702: column reference dni is ambiguous'},null,2));
}catch(error){console.error('FALLO',error.message,error.where||'');process.exitCode=1;}finally{await db.close();}
