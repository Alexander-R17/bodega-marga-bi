// Firebase identifica al usuario; el SQL privado comprueba rol y UID en cada operación.
const keyCache={expires:0,keys:[] as JsonWebKey[]};
const accountCache=new Map<string,{expires:number,uid:string}>();
const jwksUrl='https://www.googleapis.com/service_accounts/v1/jwk/securetoken@system.gserviceaccount.com';
function part(value:string){
 if(!/^[A-Za-z0-9_-]+$/.test(value))throw Error('token');
 const s=atob(value.replace(/-/g,'+').replace(/_/g,'/')+'='.repeat((4-value.length%4)%4));
 return Uint8Array.from(s,c=>c.charCodeAt(0));
}
export async function verifyFirebase(token:string,config:{project_id:string,api_key:string},http=fetch){
 const pieces=token.split('.');if(pieces.length!==3)throw Error('token');
 const header=JSON.parse(new TextDecoder().decode(part(pieces[0]))),claims=JSON.parse(new TextDecoder().decode(part(pieces[1])));
 const now=Math.floor(Date.now()/1000);
 if(header.alg!=='RS256'||typeof header.kid!=='string'||header.kid.length>200||claims.aud!==config.project_id
 ||claims.iss!=='https://securetoken.google.com/'+config.project_id||typeof claims.sub!=='string'||claims.sub.length<1||claims.sub.length>128
 ||!Number.isInteger(claims.exp)||claims.exp<=now||!Number.isInteger(claims.iat)||claims.iat>now+30
 ||!Number.isInteger(claims.auth_time)||claims.auth_time>now+30||claims.email_verified!==true||typeof claims.email!=='string')throw Error('token');
 if(keyCache.expires<Date.now()){
  const r=await http(jwksUrl,{signal:AbortSignal.timeout(10000)});if(!r.ok)throw Error('keys');
  const data=await r.json();if(!Array.isArray(data.keys))throw Error('keys');keyCache.keys=data.keys;keyCache.expires=Date.now()+300000;
 }
 const jwk=keyCache.keys.find((k:any)=>k.kid===header.kid&&k.kty==='RSA');if(!jwk)throw Error('key');
 const key=await crypto.subtle.importKey('jwk',jwk,{name:'RSASSA-PKCS1-v1_5',hash:'SHA-256'},false,['verify']);
 if(!await crypto.subtle.verify('RSASSA-PKCS1-v1_5',key,part(pieces[2]),new TextEncoder().encode(pieces[0]+'.'+pieces[1])))throw Error('signature');
 // Revocación y cuenta deshabilitada: máximo 60 segundos de caché, siempre ligada a este token verificado.
 const cached=accountCache.get(token);
 if(!cached||cached.expires<Date.now()){
  const r=await http('https://identitytoolkit.googleapis.com/v1/accounts:lookup?key='+encodeURIComponent(config.api_key),{
   method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({idToken:token}),signal:AbortSignal.timeout(10000)});
  if(!r.ok)throw Error('account');const data=await r.json();const user=data.users?.[0];
  if(!user||user.localId!==claims.sub||user.disabled||!user.emailVerified||user.email?.toLowerCase()!==claims.email.toLowerCase()
   ||(Number(user.validSince)||0)>claims.auth_time)throw Error('revoked');
  if(accountCache.size>=256)accountCache.delete(accountCache.keys().next().value!);
  accountCache.set(token,{expires:Date.now()+60000,uid:claims.sub});
 }
 return {uid:claims.sub,email:claims.email.toLowerCase()};
}
export async function handle(req:Request,env=(k:string)=>Deno.env.get(k),http=fetch,verify=verifyFirebase){
 const reply=(status:number,data:unknown)=>new Response(JSON.stringify(data),{status,headers:{'Content-Type':'application/json','Cache-Control':'no-store'}});
 if(!['GET','POST'].includes(req.method))return reply(405,{message:'Método no permitido'});
 const url=env('SUPABASE_URL'),secret=env('SUPABASE_SERVICE_ROLE_KEY');if(!url||!secret)return reply(503,{message:'Servicio sin configurar'});
 const headers:Record<string,string>={apikey:secret,'Content-Type':'application/json'};if(!secret.startsWith('sb_secret_'))headers.Authorization='Bearer '+secret;
 const rpc=async(name:string,payload:unknown)=>http(url+'/rest/v1/rpc/'+name,{method:'POST',headers,body:JSON.stringify(payload),signal:AbortSignal.timeout(15000)});
 try{
  const c=await rpc('bodega_config_movil',{});if(!c.ok)return reply(503,{message:'Ejecuta SQL 14 y activa la app desde Actividad en la web.'});
  const config=await c.json();if(!config?.project_id||!config?.api_key)return reply(503,{message:'Activa la app nativa desde Actividad en la web.'});
  if(req.method==='GET')return reply(200,{project_id:config.project_id,api_key:config.api_key,version:14});
  const auth=req.headers.get('authorization')||'';
  if(!/^Bearer [A-Za-z0-9_.-]{100,8192}$/.test(auth))return reply(401,{message:'Inicia sesión con tu cuenta de la tienda.'});
  let identity;try{identity=await verify(auth.slice(7),config,http);}catch{return reply(401,{message:'Acceso no válido. Inicia sesión otra vez y comprueba que el correo esté verificado y la cuenta habilitada.'});}
  if(!req.headers.get('content-type')?.startsWith('application/json'))return reply(415,{message:'Usa JSON'});
  const reader=req.body?.getReader();if(!reader)return reply(400,{message:'Solicitud inválida'});
  let size=0;const chunks:Uint8Array[]=[];while(true){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>32768){await reader.cancel();return reply(413,{message:'Solicitud demasiado grande'});}chunks.push(value);}
  const bytes=new Uint8Array(size);let pos=0;for(const x of chunks){bytes.set(x,pos);pos+=x.length;}
  let data;try{data=JSON.parse(new TextDecoder().decode(bytes));}catch{return reply(400,{message:'JSON inválido'});}
  const allowed=['perfil','catalogo','producto','carrito','carrito_cambiar','guardar_producto','movimiento','asociar_codigo'];
  if(!allowed.includes(data?.action)||!data.payload||typeof data.payload!=='object'||Array.isArray(data.payload))return reply(400,{message:'Acción inválida'});
  const r=await rpc('bodega_movil_api',{p_usuario:identity.uid,p_email:identity.email,p_accion:data.action,p_datos:data.payload});
  if(!r.ok){const e=await r.json().catch(()=>({}));
   const known=['Tu cuenta no tiene acceso móvil. Actualiza el equipo desde la web','Solo administración puede editar inventario','Tu rol no permite modificar la tienda',
    'El carrito cambió en otro dispositivo','El carrito está en proceso de cobro','Stock insuficiente o producto inactivo','Código no registrado en inventario',
    'El producto cambió en otro dispositivo. Recarga su ficha','Código asociado a otro producto','Código asociado a varios productos','Cantidad inválida','Precio inválido','Motivo requerido','Código duplicado'];
   const message=known.find(x=>e.message?.includes(x));
   return reply(e.code==='42501'?403:e.code==='40001'?409:r.status>=500?503:422,{message:message||'No se guardó el cambio. Revisa los campos y la disponibilidad.'});
  }
  return reply(200,{data:await r.json()});
 }catch{return reply(503,{message:'No se recibió confirmación. Reintenta la misma operación.'});}
}
// Deno entrega (Request, ServeHandlerInfo). El segundo argumento de handle es
// una dependencia interna; no debe recibir los metadatos de la conexión.
if(typeof Deno!=='undefined')Deno.serve((req:Request)=>handle(req));
