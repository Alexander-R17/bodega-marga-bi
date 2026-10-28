package pe.bodegamarga.avisos;
import android.content.Context;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;
import java.security.KeyStore;
import java.nio.charset.StandardCharsets;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;
final class AuthStore {
 static final String ALIAS="bodega-native-firebase";
 static SecretKey key()throws Exception{
  KeyStore ks=KeyStore.getInstance("AndroidKeyStore");ks.load(null);
  if(!ks.containsAlias(ALIAS)){KeyGenerator gen=KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,"AndroidKeyStore");
   gen.init(new KeyGenParameterSpec.Builder(ALIAS,KeyProperties.PURPOSE_ENCRYPT|KeyProperties.PURPOSE_DECRYPT).setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build());gen.generateKey();}
  return (SecretKey)ks.getKey(ALIAS,null);
 }
 static void save(Context c,String token)throws Exception{
  Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");cipher.init(Cipher.ENCRYPT_MODE,key());
  c.getSharedPreferences("native_auth",0).edit().putString("token",Base64.encodeToString(cipher.doFinal(token.getBytes(StandardCharsets.UTF_8)),Base64.NO_WRAP))
   .putString("iv",Base64.encodeToString(cipher.getIV(),Base64.NO_WRAP)).commit();
 }
 static String load(Context c)throws Exception{
  android.content.SharedPreferences p=c.getSharedPreferences("native_auth",0);if(!p.contains("token"))return "";
  Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");cipher.init(Cipher.DECRYPT_MODE,key(),new GCMParameterSpec(128,Base64.decode(p.getString("iv",""),Base64.NO_WRAP)));
  return new String(cipher.doFinal(Base64.decode(p.getString("token",""),Base64.NO_WRAP)),StandardCharsets.UTF_8);
 }
 static void clear(Context c){c.getSharedPreferences("native_auth",0).edit().clear().commit();}
}
