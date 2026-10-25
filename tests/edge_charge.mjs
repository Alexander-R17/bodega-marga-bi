import test from 'node:test';
import assert from 'node:assert/strict';
import {handle} from '../supabase/functions/recibir-aviso-yape/index.ts';
const env=k=>({SUPABASE_URL:'https://test.invalid',SUPABASE_SERVICE_ROLE_KEY:'sb_secret_TEST'}[k]);
const id='11111111-1111-4111-8111-111111111111';
const e={event_id:'a'.repeat(64),package:'com.bcp.innovacxion.yapeapp',amount_cents:480,notified_at:new Date().toISOString()};
const req=(body={device_id:id,event:e},auth='Bearer '+'b'.repeat(64))=>new Request('https://test.invalid',{method:'POST',headers:{'Content-Type':'application/json',Authorization:auth},body:JSON.stringify(body)});
test('sin credencial o con datos inválidos no consulta el servidor',async()=>{
 const forbidden=()=>{throw Error('No debe conectarse');};
 assert.equal((await handle(req({},''),env,forbidden)).status,401);
 for(const item of [{package:'fake.app'},{amount_cents:1.2},{notified_at:'ayer'},{event_id:'bad'}])
  assert.equal((await handle(req({device_id:id,event:{...e,...item}}),env,forbidden)).status,400);
 assert.equal((await handle(req({device_id:id,extra:'x'.repeat(2500)}),env,forbidden)).status,413);
});
test('solo reenvía campos mínimos y hash, sin clave de servidor hacia el celular',async()=>{
 let body;
 const response=await handle(req({device_id:id,event:{...e,text:'PRIVADO',sender:'NOMBRE'}}),env,async(url,options)=>{
  assert.ok(url.endsWith('/rpc/bodega_recibir_aviso'));body=JSON.parse(options.body);return Response.json({ok:true});
 });
 assert.equal(response.status,200);assert.deepEqual(body.p_evento,e);assert.match(body.p_token_hash,/^[a-f0-9]{64}$/);
 const text=await response.text();assert.equal(text.includes('sb_secret'),false);assert.equal(JSON.stringify(body).includes('PRIVADO'),false);
});
test('rechazo de dispositivo y errores temporales conservan estados distintos',async()=>{
 const r=await handle(req(),env,async()=>Response.json({code:'28000',message:'PRIVADO'},{status:400}));
 assert.equal(r.status,401);assert.equal((await r.text()).includes('PRIVADO'),false);
 const down=await handle(req(),env,async()=>{throw Error('timeout');});assert.equal(down.status,503);
});
