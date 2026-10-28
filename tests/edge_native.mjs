import test from 'node:test';import assert from 'node:assert/strict';
import {handle,verifyFirebase} from '../supabase/functions/tienda-movil/index.ts';
const env=k=>({SUPABASE_URL:'https://test.invalid',SUPABASE_SERVICE_ROLE_KEY:'sb_secret_UNIT_TEST'}[k]);
const config={project_id:'marga-test',api_key:'AIza'+'A'.repeat(35)};
const request=(data={action:'perfil',payload:{}},token='a'.repeat(120))=>new Request('https://test.invalid',{method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:JSON.stringify(data)});
const pair=await crypto.subtle.generateKey({name:'RSASSA-PKCS1-v1_5',modulusLength:2048,publicExponent:new Uint8Array([1,0,1]),hash:'SHA-256'},true,['sign','verify']);
const jwk={...await crypto.subtle.exportKey('jwk',pair.publicKey),kid:'synthetic-key',alg:'RS256'};
const base64=x=>Buffer.from(x).toString('base64url');
async function token(extra={},head={}){const now=Math.floor(Date.now()/1000);const header=base64(JSON.stringify({alg:'RS256',kid:jwk.kid,...head}));const body=base64(JSON.stringify({aud:config.project_id,iss:'https://securetoken.google.com/'+config.project_id,sub:'cash',iat:now-5,auth_time:now-60,exp:now+3500,email:'cash@example.invalid',email_verified:true,...extra}));const input=header+'.'+body;const signature=await crypto.subtle.sign('RSASSA-PKCS1-v1_5',pair.privateKey,new TextEncoder().encode(input));return input+'.'+base64(signature);}
const google=(change={})=>async url=>url.includes('/jwk/')?Response.json({keys:[jwk]}):Response.json({users:[{localId:'cash',email:'cash@example.invalid',emailVerified:true,validSince:'1',...change}]});
test('verifica firma RSA real, issuer y audiencia Firebase con claves sintéticas',async()=>{
 const valid=await token({nonce:'good'});assert.deepEqual(await verifyFirebase(valid,config,google()),{uid:'cash',email:'cash@example.invalid'});
 for(const claims of [{aud:'otro-proyecto'},{iss:'https://fake.invalid'},{email_verified:false},{exp:1}])await assert.rejects(()=>token(claims).then(t=>verifyFirebase(t,config,google())));
 await assert.rejects(()=>token({}, {alg:'HS256'}).then(t=>verifyFirebase(t,config,google())));
 const bad=valid.slice(0,valid.lastIndexOf('.')+1)+base64('fake');await assert.rejects(()=>verifyFirebase(bad,config,google()));
});
test('rechaza usuario deshabilitado y token revocado aunque la firma sea válida',async()=>{
 await assert.rejects(()=>token({nonce:'disabled'}).then(t=>verifyFirebase(t,config,google({disabled:true}))));
 await assert.rejects(()=>token({nonce:'revoked'}).then(t=>verifyFirebase(t,config,google({validSince:String(Math.floor(Date.now()/1000))}))));
});
test('bootstrap solo publica configuración Firebase pública',async()=>{
 const r=await handle(new Request('https://test.invalid'),env,async()=>Response.json({...config,private_key:'PRIVADO',service_role:'SECRETO'}));
 assert.equal(r.status,200);assert.deepEqual(await r.json(),{...config,version:14});
});
test('acciones usan UID verificado y no reenvían una identidad del cliente',async()=>{
 let payload;const r=await handle(request({action:'perfil',payload:{uid:'admin',rol:'administrador'},uid:'admin'}),env,async(url,o)=>{
  if(url.endsWith('/bodega_config_movil'))return Response.json(config);payload=JSON.parse(o.body);return Response.json({nombre:'Persona Prueba'});
 },async()=>({uid:'cash',email:'cash@example.invalid'}));
 assert.equal(r.status,200);assert.equal(payload.p_usuario,'cash');assert.equal(payload.p_email,'cash@example.invalid');
 assert.equal((await r.text()).includes('sb_secret'),false);
});
test('sin sesión, acciones desconocidas y cuerpo excesivo no ejecutan operaciones',async()=>{
 let actions=0;const http=async u=>{if(u.endsWith('/bodega_config_movil'))return Response.json(config);actions++;return Response.json({});};const verify=async()=>({uid:'cash',email:'cash@example.invalid'});
 assert.equal((await handle(request({},''),env,http,verify)).status,401);
 assert.equal((await handle(request({action:'activar_movil',payload:{}}),env,http,verify)).status,400);
 assert.equal((await handle(request({action:'perfil',payload:{x:'x'.repeat(34000)}}),env,http,verify)).status,413);
 assert.equal(actions,0);
});
test('conflictos, permisos y fallos transitorios mantienen respuestas distintas',async()=>{
 const run=e=>handle(request(),env,async u=>u.endsWith('/bodega_config_movil')?Response.json(config):Response.json(e,{status:400}),async()=>({uid:'cash',email:'cash@example.invalid'}));
 assert.equal((await run({code:'40001',message:'El carrito cambió en otro dispositivo'})).status,409);
 assert.equal((await run({code:'42501',message:'PRIVADO'})).status,403);
 assert.equal((await handle(request(),env,async()=>{throw Error('network');})).status,503);
});
