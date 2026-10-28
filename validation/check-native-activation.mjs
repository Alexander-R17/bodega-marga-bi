import {PGlite} from '@electric-sql/pglite';
import {readFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';

const root=fileURLToPath(new URL('../',import.meta.url));
const db=new PGlite();
const main=readFileSync(root+'database/14_app_nativa_y_carrito.sql','utf8');
const patch=readFileSync(root+'database/15_corregir_activacion_movil.sql','utf8');
const scalar=async(q,p=[])=>Object.values((await db.query(q,p)).rows[0])[0];
const admin={uid:'admin-test',email:'admin@example.invalid',nombre:'Administración de prueba',rol:'administrador'};
const cash={uid:'cash-test',email:'cash@example.invalid',nombre:'Caja de prueba',rol:'cajero'};
const activate=team=>scalar('select public.bodega_activar_movil($1,$2,$3,$4)',[
  'marga-prueba','AIza'+'A'.repeat(35),JSON.stringify(team),admin.uid,
]);
try {
  await db.exec('create role anon; create role authenticated; create role service_role bypassrls;');
  await db.exec(main.slice(0,main.indexOf('create table if not exists public.bodega_carritos'))+'commit;');
  await db.exec(patch);await db.exec(patch);
  assert.equal(await scalar('select count(*) from public.bodega_movil_equipo'),0);
  console.log('PASS SQL 15 repetible; no crea cuentas ni configuración al instalar');

  const definition=await scalar("select pg_get_functiondef('public.bodega_activar_movil(text,text,jsonb,text)'::regprocedure)");
  assert.match(definition,/update bodega_movil_equipo set activo=false where activo is true;/);
  assert.doesNotMatch(patch,/set\s+safeupdate|disable\s+row\s+level\s+security/i);
  console.log('PASS la actualización tiene filtro explícito sin desactivar safeupdate ni RLS (contrato estático)');

  assert.equal((await activate([admin,cash])).cuentas,2);
  assert.equal(await scalar('select count(*) from public.bodega_movil_equipo where activo'),2);
  await activate([admin]);
  assert.equal(await scalar('select activo from public.bodega_movil_equipo where uid=$1',[cash.uid]),false);
  assert.equal(await scalar('select activo from public.bodega_movil_equipo where uid=$1',[admin.uid]),true);
  await activate([admin,cash]);await activate([admin,cash]);
  assert.equal(await scalar('select count(*) from public.bodega_movil_equipo'),2);
  assert.equal(await scalar('select count(*) from public.bodega_movil_equipo where activo'),2);
  console.log('PASS activación repetida, retiro y reincorporación conservan UID y no duplican cuentas');

  await assert.rejects(()=>activate([cash]),/administrador/);
  await assert.rejects(()=>activate([admin,{...cash,rol:'root'}]),/Equipo móvil inválido/);
  assert.equal(await scalar('select count(*) from public.bodega_movil_equipo where activo'),2);
  console.log('PASS equipo inválido se revierte completo sin desactivar cuentas autorizadas');

  for(const role of ['anon','authenticated']){
    await db.exec('set role '+role);await assert.rejects(()=>activate([admin,cash]),/permission denied/);
    await db.exec('reset role');
  }
  await db.exec('set role service_role');assert.equal((await activate([admin,cash])).ok,true);
  await db.exec('reset role');
  console.log('PASS activación privada: anon y authenticated no pueden ejecutarla; service_role sí');
  console.log('NOTA: PGlite no carga la extensión nativa safeupdate; su requisito WHERE se verifica en la definición SQL.');
} catch(error) {
  console.error(error.stack);process.exitCode=1;
} finally {await db.close();}
