import test from 'node:test';
import assert from 'node:assert/strict';

test('la entrada Deno ignora ServeHandlerInfo y conserva la configuración del servidor', async () => {
  const originalDeno = globalThis.Deno;
  const originalFetch = globalThis.fetch;
  let entry;
  let calls = 0;
  globalThis.Deno = {
    env: { get: key => ({ SUPABASE_URL: 'https://test.invalid', SUPABASE_SERVICE_ROLE_KEY: 'sb_secret_UNIT_TEST' }[key]) },
    serve: handler => { entry = handler; },
  };
  globalThis.fetch = async (url, options) => {
    calls++;
    assert.equal(url, 'https://test.invalid/rest/v1/rpc/bodega_config_movil');
    assert.equal(options.headers.apikey, 'sb_secret_UNIT_TEST');
    return Response.json({ project_id: 'bodega-test', api_key: 'PUBLIC_TEST_KEY' });
  };
  try {
    await import('../supabase/functions/tienda-movil/index.ts?entry-regression');
    assert.equal(typeof entry, 'function', 'El módulo desplegado debe registrar un manejador HTTP');
    const response = await entry(new Request('https://test.invalid/functions/v1/tienda-movil'), {
      remoteAddr: { transport: 'tcp', hostname: '127.0.0.1', port: 12345 },
      completed: Promise.resolve(),
    });
    assert.equal(response.status, 200);
    assert.deepEqual(await response.json(), { project_id: 'bodega-test', api_key: 'PUBLIC_TEST_KEY', version: 14 });
    assert.equal(calls, 1);
  } finally {
    globalThis.fetch = originalFetch;
    if (originalDeno === undefined) delete globalThis.Deno;
    else globalThis.Deno = originalDeno;
  }
});
