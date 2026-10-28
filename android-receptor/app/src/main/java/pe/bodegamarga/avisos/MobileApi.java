package pe.bodegamarga.avisos;
import android.content.Context;
import org.json.JSONObject;
import java.io.InputStream;
import java.io.ByteArrayOutputStream;
import java.net.URL;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import javax.net.ssl.HttpsURLConnection;
final class MobileApi {
 static final class Failure extends Exception {
  final int status;final boolean confirmed;
  Failure(int status,String message){super(message);this.status=status;confirmed=status>=400&&status<500&&status!=408;}
 }
 final Context context;String endpoint,project,key,token="";long expires;
 MobileApi(Context c){context=c.getApplicationContext();endpoint=context.getSharedPreferences("native_shop",0).getString("endpoint","");
  if(endpoint.isEmpty())try{endpoint=Config.load(context).endpoint.replace("recibir-aviso-yape","tienda-movil");}catch(Exception ignored){}
 }
 static boolean endpointValid(String value){return value!=null&&value.matches("https://[a-z0-9]{10,40}\\.supabase\\.co/functions/v1/tienda-movil");}
 void configure(String value)throws Exception {
  value=value.trim();if(!endpointValid(value))throw new Failure(400,"Usa la dirección tienda-movil de tu Supabase.");
  if(!value.equals(endpoint)){logout();context.getSharedPreferences("native_shop",0).edit().remove("pending").commit();}
  endpoint=value;context.getSharedPreferences("native_shop",0).edit().putString("endpoint",value).commit();bootstrap();
 }
 JSONObject http(String url,String method,String body,String bearer,String contentType)throws Exception{
  HttpsURLConnection c=(HttpsURLConnection)new URL(url).openConnection();
  try{
   c.setInstanceFollowRedirects(false);c.setConnectTimeout(12000);c.setReadTimeout(18000);c.setRequestMethod(method);c.setRequestProperty("Accept","application/json");
   if(bearer!=null)c.setRequestProperty("Authorization","Bearer "+bearer);
   if(body!=null){c.setDoOutput(true);c.setRequestProperty("Content-Type",contentType);byte[] bytes=body.getBytes(StandardCharsets.UTF_8);c.setFixedLengthStreamingMode(bytes.length);try(java.io.OutputStream out=c.getOutputStream()){out.write(bytes);}}
   int code=c.getResponseCode();InputStream stream=code>=200&&code<300?c.getInputStream():c.getErrorStream();ByteArrayOutputStream out=new ByteArrayOutputStream();
   if(stream!=null)try(InputStream input=stream){byte[] b=new byte[4096];int n;while((n=input.read(b))!=-1){out.write(b,0,n);if(out.size()>1048576)throw new Failure(503,"Respuesta demasiado grande.");}}
   JSONObject result;try{result=new JSONObject(out.toString(StandardCharsets.UTF_8.name()));}catch(Exception e){throw new Failure(code==200?503:code,"No se pudo leer la respuesta del servidor.");}
   if(code<200||code>=300){
    String message=result.optString("message","");
    if(!url.startsWith(endpoint)){message="No se pudo autenticar. Revisa correo, contraseña, verificación y conexión.";}
    else if(code==404)message="Falta desplegar la función tienda-movil. Instala la actualización web 14.";
    if(message.isEmpty())message="No se guardó el cambio. Revisa la configuración y la conexión.";
    throw new Failure(code,message);
   }return result;
  }finally{c.disconnect();}
 }
 void bootstrap()throws Exception{
  if(!endpointValid(endpoint))throw new Failure(400,"Configura primero la tienda con la dirección de Supabase.");
  JSONObject b=http(endpoint,"GET",null,null,null);project=b.getString("project_id");key=b.getString("api_key");
 }
 void tokens(JSONObject data,boolean refreshed)throws Exception{
  token=data.getString(refreshed?"id_token":"idToken");String refresh=data.getString(refreshed?"refresh_token":"refreshToken");
  expires=System.currentTimeMillis()+(data.optLong(refreshed?"expires_in":"expiresIn",3600)-60)*1000;AuthStore.save(context,refresh);
 }
 JSONObject login(String email,String password)throws Exception{
  bootstrap();JSONObject data=http("https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key="+URLEncoder.encode(key,"UTF-8"),"POST",
   new JSONObject().put("email",email.trim()).put("password",password).put("returnSecureToken",true).toString(),null,"application/json");
  tokens(data,false);
  try{return call("perfil",new JSONObject());}catch(Exception e){logout();throw e;}
 }
 void refresh()throws Exception{
  if(key==null)bootstrap();String refresh=AuthStore.load(context);if(refresh.isEmpty())throw new Failure(401,"Inicia sesión con tu cuenta de la tienda.");
  tokens(http("https://securetoken.googleapis.com/v1/token?key="+URLEncoder.encode(key,"UTF-8"),"POST","grant_type=refresh_token&refresh_token="+URLEncoder.encode(refresh,"UTF-8"),null,"application/x-www-form-urlencoded"),true);
 }
 JSONObject call(String action,JSONObject payload)throws Exception{
  if(token.isEmpty()||System.currentTimeMillis()>=expires)refresh();
  String body=new JSONObject().put("action",action).put("payload",payload).toString();
  try{return http(endpoint,"POST",body,token,"application/json").getJSONObject("data");}
  catch(Failure e){if(e.status!=401)throw e;refresh();return http(endpoint,"POST",body,token,"application/json").getJSONObject("data");}
 }
 void logout(){token="";expires=0;AuthStore.clear(context);}
}
