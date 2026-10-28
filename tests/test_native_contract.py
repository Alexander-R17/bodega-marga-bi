from pathlib import Path
from pglast import parse_sql

ROOT=Path(__file__).resolve().parents[1]
JAVA=ROOT/'android-receptor/app/src/main/java/pe/bodegamarga/avisos'

def test_mobile_screens_use_native_widgets_and_no_browser_component():
    for name in ['MainActivity.java','NativeUi.java','ScanActivity.java']:
        source=(JAVA/name).read_text()
        assert 'import android.webkit' not in source
        assert 'new WebView' not in source
        assert 'Intent.ACTION_VIEW' not in source
    assert 'LinearLayout' in (JAVA/'NativeUi.java').read_text()
    assert 'EditText' in (JAVA/'MainActivity.java').read_text()

def test_native_session_keeps_refresh_token_encrypted_without_saving_password():
    store=(JAVA/'AuthStore.java').read_text();api=(JAVA/'MobileApi.java').read_text()
    assert 'AndroidKeyStore' in store and 'AES/GCM/NoPadding' in store
    assert 'AuthStore.save(context,refresh)' in api
    assert 'putString("password"' not in api
    assert 'service_role' not in api and 'SUPABASE_SERVICE_ROLE_KEY' not in api

def test_migration_parses_and_new_endpoint_has_explicit_firebase_auth():
    parse_sql((ROOT/'database/14_app_nativa_y_carrito.sql').read_text())
    endpoint=(ROOT/'supabase/functions/tienda-movil/index.ts').read_text()
    assert "crypto.subtle.verify" in endpoint
    assert "claims.aud!==config.project_id" in endpoint
    assert "p_usuario:identity.uid" in endpoint

def test_demo_can_search_a_client_with_optional_name():
    from bodega.demo import DemoRepository
    r=DemoRepository()
    r.sale('optional-name',[{'producto_id':1,'cantidad':1,'descuento':0}],'Efectivo',confirmed_total=4.8,customer={'dni':'01234567','nombre':''})
    assert r.search_customers('01234567')[0]['dni']=='01234567'
