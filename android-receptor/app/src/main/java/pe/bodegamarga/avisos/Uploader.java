package pe.bodegamarga.avisos;

import android.content.Context;
import org.json.JSONObject;
import java.net.URL;
import javax.net.ssl.HttpsURLConnection;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.function.BooleanSupplier;

final class Uploader {
    static final ExecutorService EXEC=Executors.newSingleThreadExecutor();
    static void status(Context c,String text){Config.prefs(c).edit().putString("status",text).apply();}
    private static int send(Config config,JSONObject event)throws Exception{
        JSONObject body=new JSONObject();body.put("device_id",config.device);body.put("event",event==null?JSONObject.NULL:event);
        byte[] bytes=body.toString().getBytes(StandardCharsets.UTF_8);
        HttpsURLConnection http=(HttpsURLConnection)new URL(config.endpoint).openConnection();
        http.setInstanceFollowRedirects(false);http.setConnectTimeout(10000);http.setReadTimeout(10000);
        http.setRequestMethod("POST");http.setDoOutput(true);http.setRequestProperty("Content-Type","application/json");
        http.setRequestProperty("Authorization","Bearer "+config.token);http.setFixedLengthStreamingMode(bytes.length);
        try{
            try(java.io.OutputStream output=http.getOutputStream()){output.write(bytes);}
            return http.getResponseCode();
        }finally{http.disconnect();}
    }
    static boolean drain(Context c,boolean ping){return drain(c,ping,()->true);}
    /** true pide reintento; false indica terminado o pausado. */
    static boolean drain(Context c,boolean ping,BooleanSupplier allowed){
        if(!Config.enabled(c)||!allowed.getAsBoolean())return false;
        try(QueueDb queue=new QueueDb(c)){
            Config config=Config.load(c);boolean needsReview=false;
            for(QueueDb.Event e:queue.pending(config.device)){
                if(!Config.enabled(c)||!allowed.getAsBoolean()||!config.device.equals(Config.prefs(c).getString("device","")))return false;
                if(System.currentTimeMillis()-e.time>24L*3600000){queue.mark(e.id,"EXPIRED");needsReview=true;continue;}
                JSONObject event=new JSONObject();event.put("event_id",e.id);event.put("package",PaymentParser.PACKAGE);
                event.put("amount_cents",e.cents);event.put("notified_at",Instant.ofEpochMilli(e.time).toString());
                int code=send(config,event);
                if(code==200){queue.mark(e.id,"SENT");Config.prefs(c).edit().putLong("last_sent",System.currentTimeMillis()).apply();}
                else if(code==401||code==403){disable(c);return false;}
                else if(code==400||code==413||code==415||code==422){queue.mark(e.id,"REJECTED");needsReview=true;}
                else{connectionError(c,code);return true;}
            }
            if(!queue.pending(config.device).isEmpty())return true;
            if(ping&&Config.enabled(c)&&allowed.getAsBoolean()){
                int code=send(config,null);
                if(code==401||code==403){disable(c);return false;}
                if(code!=200){connectionError(c,code);return true;}
                Config.prefs(c).edit().putLong("last_contact",System.currentTimeMillis()).apply();
            }
            status(c,needsReview?"Conexión realizada; revisa los avisos REJECTED o EXPIRED y la hora automática del celular.":"Conexión correcta. El servidor recibió la solicitud; consulta la orden desde caja.");return false;
        }catch(Exception error){status(c,"Envío pendiente. Comprueba internet y el vínculo; se reintentará.");return true;}
    }
    private static void disable(Context c){
        Config.prefs(c).edit().putBoolean("enabled",false).apply();
        status(c,"Servidor rechazó el vínculo (401/403). Revisa el JSON y Verify JWT de la función; vuelve a activar después.");
    }
    private static void connectionError(Context c,int code){
        status(c,code==404?"No se encontró recibir-aviso-yape (404). Despliega la Edge Function en tu Supabase.":"Servidor no disponible (HTTP "+code+"). Se conservan los pendientes para reintentar.");
    }
    private Uploader(){}
}
