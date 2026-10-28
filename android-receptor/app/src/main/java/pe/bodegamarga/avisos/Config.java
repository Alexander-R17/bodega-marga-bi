package pe.bodegamarga.avisos;

import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;
import org.json.JSONObject;
import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

final class Config {
    private static final String ALIAS="bodega-receptor-v1";
    final String endpoint,device,token;
    Config(String endpoint,String device,String token){
        if(!endpoint.matches("https://[a-z0-9]{10,40}\\.supabase\\.co/functions/v1/recibir-aviso-yape")||
           !device.matches("(?i)[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")||!token.matches("[a-f0-9]{64}"))
            throw new IllegalArgumentException("Archivo de vínculo inválido");
        this.endpoint=endpoint;this.device=device;this.token=token;
    }
    static SharedPreferences prefs(Context c){return c.getSharedPreferences("receptor",Context.MODE_PRIVATE);}
    static boolean enabled(Context c){return prefs(c).getBoolean("enabled",false);}
    private static SecretKey key()throws Exception{
        KeyStore ks=KeyStore.getInstance("AndroidKeyStore");ks.load(null);
        if(!ks.containsAlias(ALIAS)){
            KeyGenerator g=KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,"AndroidKeyStore");
            g.init(new KeyGenParameterSpec.Builder(ALIAS,KeyProperties.PURPOSE_ENCRYPT|KeyProperties.PURPOSE_DECRYPT)
              .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build());g.generateKey();
        }
        return(SecretKey)ks.getKey(ALIAS,null);
    }
    static void save(Context c,JSONObject data)throws Exception{
        Config config=new Config(data.getString("endpoint"),data.getString("device_id"),data.getString("token"));
        Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");cipher.init(Cipher.ENCRYPT_MODE,key());
        String encrypted=Base64.encodeToString(cipher.doFinal(config.token.getBytes(StandardCharsets.UTF_8)),Base64.NO_WRAP);
        prefs(c).edit().putString("endpoint",config.endpoint).putString("device",config.device).putString("token",encrypted)
         .putString("iv",Base64.encodeToString(cipher.getIV(),Base64.NO_WRAP)).putBoolean("enabled",false)
         .putLong("paired_at",System.currentTimeMillis()).putString("status","Vínculo importado. Falta autorizar y activar el lector.").commit();
    }
    static Config load(Context c)throws Exception{
        SharedPreferences p=prefs(c);Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.DECRYPT_MODE,key(),new GCMParameterSpec(128,Base64.decode(p.getString("iv",""),Base64.NO_WRAP)));
        String token=new String(cipher.doFinal(Base64.decode(p.getString("token",""),Base64.NO_WRAP)),StandardCharsets.UTF_8);
        return new Config(p.getString("endpoint",""),p.getString("device",""),token);
    }
}
