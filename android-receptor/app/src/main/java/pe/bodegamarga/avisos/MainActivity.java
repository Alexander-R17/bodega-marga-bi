package pe.bodegamarga.avisos;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.NotificationManager;
import android.content.ComponentName;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.provider.Settings;
import android.view.WindowInsets;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;
import org.json.JSONObject;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.text.DateFormat;
import java.util.Date;

public final class MainActivity extends Activity {
    private TextView status;private CheckBox active;private boolean refreshing;
    private int dp(int value){return Math.round(value*getResources().getDisplayMetrics().density);}
    private void text(LinearLayout root,String message,int size){
        TextView view=new TextView(this);view.setText(message);view.setTextSize(size);view.setTextColor(Color.rgb(23,59,50));
        view.setPadding(0,dp(7),0,dp(7));root.addView(view);
    }
    private void button(LinearLayout root,String label,Runnable action){Button b=new Button(this);b.setText(label);root.addView(b);b.setOnClickListener(v->action.run());}
    private boolean access(){return((NotificationManager)getSystemService(NOTIFICATION_SERVICE)).isNotificationListenerAccessGranted(new ComponentName(this,YapeListener.class));}
    private void message(String value){Toast.makeText(this,value,Toast.LENGTH_LONG).show();}
    private void refreshLater(){runOnUiThread(()->{if(!isFinishing()&&!isDestroyed())refresh();});}
    @Override public void onCreate(Bundle state){
        super.onCreate(state);
        ScrollView scroll=new ScrollView(this);LinearLayout root=new LinearLayout(this);root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(22),dp(20),dp(22),dp(30));root.setBackgroundColor(Color.rgb(246,244,235));scroll.addView(root);setContentView(scroll);
        scroll.setOnApplyWindowInsetsListener((view,insets)->{
            if(Build.VERSION.SDK_INT>=30){android.graphics.Insets bars=insets.getInsets(WindowInsets.Type.systemBars());view.setPadding(bars.left,bars.top,bars.right,bars.bottom);}
            else view.setPadding(insets.getSystemWindowInsetLeft(),insets.getSystemWindowInsetTop(),insets.getSystemWindowInsetRight(),insets.getSystemWindowInsetBottom());
            return insets;
        });
        text(root,"BODEGA MARGA\nTu celular receptor",26);
        text(root,"Avisos Yape · piloto 0.2",16);
        text(root,"Instala este lector en el celular que recibe el dinero. Detecta avisos; no consulta el saldo ni aprueba una venta por sí solo. Es una app propia del proyecto, sin afiliación con Yape o BCP.",16);
        text(root,"Android concede acceso amplio a notificaciones. Este código procesa solo Yape y envía importe, hora e identificador técnico. No envía nombres, el texto del aviso ni códigos de seguridad. Puedes pausar el lector o retirar el permiso en Ajustes.",15);
        button(root,"1 · Importar vínculo privado",()->{
            Intent i=new Intent(Intent.ACTION_OPEN_DOCUMENT);i.setType("*/*");i.addCategory(Intent.CATEGORY_OPENABLE);
            i.putExtra(Intent.EXTRA_MIME_TYPES,new String[]{"application/json","application/octet-stream","text/plain"});startActivityForResult(i,10);
        });
        button(root,"2 · Dar acceso a notificaciones",()->startActivity(new Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS)));
        active=new CheckBox(this);active.setText("3 · Activar lectura y envío de Yape");active.setTextColor(Color.rgb(23,59,50));root.addView(active);
        active.setOnCheckedChangeListener((widget,checked)->{
            if(refreshing)return;
            if(checked){
                try{Config.load(this);if(!access())throw new IllegalStateException();}
                catch(Exception error){message("Importa el vínculo y concede el acceso primero.");refresh();return;}
            }
            Config.prefs(this).edit().putBoolean("enabled",checked).apply();
            if(checked){UploadJob.schedule(this);UploadJob.retry(this);}else UploadJob.cancel(this);
            refresh();
        });
        button(root,"Comprobar conexión y enviar pendientes",()->{
            if(!Config.enabled(this)){message("Activa el lector primero.");return;}
            Uploader.status(this,"Comprobando conexión…");refresh();
            Uploader.EXEC.execute(()->{if(Uploader.drain(getApplicationContext(),true))UploadJob.retry(getApplicationContext());refreshLater();});
        });
        button(root,"Abrir ajustes de batería de esta app",()->startActivity(new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,Uri.parse("package:"+getPackageName()))));
        text(root,"En el Samsung: Batería → Límites de uso en segundo plano → Apps sin suspensión. Añade este lector. Revisa también las notificaciones de Yape y la fecha/hora automáticas; los nombres pueden variar según One UI.",15);
        button(root,"Actualizar estado",this::refresh);
        status=new TextView(this);status.setTextSize(15);status.setTextColor(Color.rgb(23,59,50));status.setPadding(0,dp(12),0,dp(12));root.addView(status);
        button(root,"Eliminar vínculo de este celular",()->new AlertDialog.Builder(this)
            .setMessage("Se borrarán la credencial y la cola local. Revoca también el vínculo en Actividad de tu sistema. Esta acción no anula ventas ni devuelve dinero.")
            .setPositiveButton("Eliminar",(dialog,which)->{
                Config.prefs(this).edit().putBoolean("enabled",false).apply();UploadJob.cancel(this);
                Uploader.EXEC.execute(()->{Config.prefs(getApplicationContext()).edit().clear().commit();deleteDatabase("avisos.db");refreshLater();});
            }).setNegativeButton("Cancelar",null).show());
        text(root,"PENDING: pendiente · SENT: enviado · REJECTED: rechazado · EXPIRED: vencido. Un envío correcto no demuestra que el importe corresponda a una venta determinada.",13);
    }
    @Override protected void onResume(){super.onResume();if(status!=null)refresh();}
    private String date(long value){return value==0?"sin registros":DateFormat.getDateTimeInstance().format(new Date(value));}
    private void refresh(){
        refreshing=true;active.setChecked(Config.enabled(this));refreshing=false;
        String queue;try(QueueDb db=new QueueDb(this)){queue=db.summary();}
        status.setText("Acceso a notificaciones: "+(access()?"concedido":"pendiente")+"\nVínculo: "+
            (Config.prefs(this).contains("device")?"importado":"pendiente")+"\nLector: "+(Config.enabled(this)?"activado":"pausado")+
            "\nÚltimo aviso Yape: "+date(Config.prefs(this).getLong("last_yape",0))+"\n"+Config.prefs(this).getString("last_parse","")+
            "\nÚltimo envío: "+date(Config.prefs(this).getLong("last_sent",0))+
            "\nÚltima comprobación de conexión: "+date(Config.prefs(this).getLong("last_contact",0))+
            "\n\n"+Config.prefs(this).getString("status","")+"\n\n"+queue);
    }
    @Override protected void onActivityResult(int request,int result,Intent intent){
        super.onActivityResult(request,result,intent);
        if(request!=10||result!=RESULT_OK||intent==null||intent.getData()==null)return;
        try(InputStream input=getContentResolver().openInputStream(intent.getData())){
            if(input==null)throw new IllegalArgumentException();
            byte[] buffer=new byte[4097];int count=0,n;
            while(count<buffer.length&&(n=input.read(buffer,count,buffer.length-count))!=-1)count+=n;
            if(count==buffer.length)throw new IllegalArgumentException();
            JSONObject data=new JSONObject(new String(buffer,0,count,StandardCharsets.UTF_8));
            new Config(data.getString("endpoint"),data.getString("device_id"),data.getString("token"));
            new AlertDialog.Builder(this).setTitle("Vincular este proyecto")
                .setMessage(data.getString("endpoint")+"\n\nConfirma que es tu Supabase. Se borrarán los avisos locales del vínculo anterior.")
                .setPositiveButton("Vincular",(dialog,which)->{
                    Config.prefs(this).edit().putBoolean("enabled",false).apply();UploadJob.cancel(this);
                    Uploader.EXEC.execute(()->{
                        try{Config.save(getApplicationContext(),data);deleteDatabase("avisos.db");refreshLater();}
                        catch(Exception error){runOnUiThread(()->message("No se pudo guardar el vínculo. Vuelve a importarlo."));}
                    });
                }).setNegativeButton("Cancelar",null).show();
        }catch(Exception error){message("Archivo inválido. Descarga el vínculo desde Actividad de tu sistema.");}
    }
}
