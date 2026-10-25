// Compatible con device_id, token y event del APK piloto anterior. No registra ventas.
export async function handle(req: Request, env = (key: string) => Deno.env.get(key), http = fetch) {
 const reply=(status:number,message:string)=>new Response(JSON.stringify({ok:status===200,message}),{status,headers:{'Content-Type':'application/json','Cache-Control':'no-store'}});
 if(req.method!=='POST')return reply(405,'Solo POST');
 const auth=req.headers.get('authorization')||'';
 if(!/^Bearer [a-f0-9]{64}$/.test(auth))return reply(401,'Receptor no autorizado');
 if(!req.headers.get('content-type')?.startsWith('application/json'))return reply(415,'Usa JSON');
 const reader=req.body?.getReader();if(!reader)return reply(400,'Solicitud inválida');
 let size=0;const chunks:Uint8Array[]=[];
 while(true){const {done,value}=await reader.read();if(done)break;size+=value.length;
  if(size>2048){await reader.cancel();return reply(413,'Cuerpo demasiado grande');}chunks.push(value);}
 const bytes=new Uint8Array(size);let at=0;for(const part of chunks){bytes.set(part,at);at+=part.length;}
 let data;try{data=JSON.parse(new TextDecoder().decode(bytes));}catch{return reply(400,'JSON inválido');}
 if(typeof data?.device_id!=='string'||!/^[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}$/i.test(data.device_id))return reply(400,'Dispositivo inválido');
 const e=data.event??null;
 if(e!==null&&(e.package!=='com.bcp.innovacxion.yapeapp'||typeof e.event_id!=='string'||!/^[a-f0-9]{64}$/.test(e.event_id)
 ||!Number.isInteger(e.amount_cents)||e.amount_cents<1||e.amount_cents>10000000||typeof e.notified_at!=='string'
 ||e.notified_at.length>40||!/^\d{4}-\d\d-\d\dT.*(?:Z|[+-]\d\d:\d\d)$/.test(e.notified_at)||!Number.isFinite(Date.parse(e.notified_at))))return reply(400,'Aviso inválido');
 const url=env('SUPABASE_URL'),key=env('SUPABASE_SERVICE_ROLE_KEY');if(!url||!key)return reply(503,'Servicio no configurado');
 const hash=[...new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(auth.slice(7))))].map(x=>x.toString(16).padStart(2,'0')).join('');
 const headers:Record<string,string>={apikey:key,'Content-Type':'application/json'};if(!key.startsWith('sb_secret_'))headers.Authorization=`Bearer ${key}`;
 try{
  const r=await http(`${url}/rest/v1/rpc/bodega_recibir_aviso`,{method:'POST',headers,signal:AbortSignal.timeout(10000),
   body:JSON.stringify({p_dispositivo:data.device_id,p_token_hash:hash,p_evento:e===null?null:{event_id:e.event_id,package:e.package,amount_cents:e.amount_cents,notified_at:e.notified_at}})});
  if(!r.ok){const error=await r.json().catch(()=>({}));return reply(error.code==='28000'?401:error.message==='Límite de avisos'?429:r.status>=500?503:422,'Aviso no aceptado');}
  return reply(200,'Aviso recibido para revisión');
 }catch{return reply(503,'Reintenta más tarde');}
}
if(typeof Deno!=='undefined')Deno.serve(req=>handle(req));
