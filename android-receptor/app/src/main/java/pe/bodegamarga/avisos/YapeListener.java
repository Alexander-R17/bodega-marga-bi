package pe.bodegamarga.avisos;

import android.app.Notification;
import android.service.notification.NotificationListenerService;
import android.service.notification.StatusBarNotification;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Locale;

public final class YapeListener extends NotificationListenerService {
    @Override public void onListenerConnected(){UploadJob.schedule(this);}
    @Override public void onNotificationPosted(StatusBarNotification sbn){
        // Descartar otras aplicaciones ANTES de leer extras.
        if(!Config.enabled(this)||!PaymentParser.PACKAGE.equals(sbn.getPackageName()))return;
        Notification n=sbn.getNotification();if((n.flags&Notification.FLAG_GROUP_SUMMARY)!=0)return;
        long posted=sbn.getPostTime();
        if(posted<Config.prefs(this).getLong("paired_at",Long.MAX_VALUE))return;
        String title=String.valueOf(n.extras.getCharSequence(Notification.EXTRA_TITLE,""));
        String text=String.valueOf(n.extras.getCharSequence(Notification.EXTRA_BIG_TEXT,n.extras.getCharSequence(Notification.EXTRA_TEXT,"")));
        Integer cents=PaymentParser.parse(sbn.getPackageName(),title,text);
        Config.prefs(this).edit().putLong("last_yape",System.currentTimeMillis())
          .putString("last_parse",cents==null?"Formato no reconocido: no se envió el texto.":"Aviso de recepción reconocido.").apply();
        if(cents==null)return;
        // ID técnico del aviso, no identificador bancario. when ayuda con actualizaciones de la misma notificación.
        long identityTime=n.when>0?n.when:posted;
        String identity=sbn.getKey()+"|"+identityTime+"|"+cents;
        Uploader.EXEC.execute(()->{
            if(!Config.enabled(getApplicationContext()))return;
            if(posted<Config.prefs(getApplicationContext()).getLong("paired_at",Long.MAX_VALUE))return;
            try(QueueDb db=new QueueDb(getApplicationContext())){
                Config config=Config.load(getApplicationContext());
                byte[] digest=MessageDigest.getInstance("SHA-256").digest(identity.getBytes(StandardCharsets.UTF_8));
                StringBuilder id=new StringBuilder();for(byte b:digest)id.append(String.format(Locale.ROOT,"%02x",b&255));
                // Guardar la hora de publicación del primer aviso, en milisegundos.
                db.add(new QueueDb.Event(id.toString(),config.device,cents,posted));
            }catch(Exception error){Uploader.status(getApplicationContext(),"No se pudo guardar el aviso local. Revisa el vínculo o el almacenamiento.");return;}
            if(Uploader.drain(getApplicationContext(),false))UploadJob.retry(getApplicationContext());
        });
    }
}
