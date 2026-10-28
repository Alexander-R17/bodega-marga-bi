package pe.bodegamarga.avisos;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

public final class BootReceiver extends BroadcastReceiver {
    @Override public void onReceive(Context c,Intent intent){
        if(Intent.ACTION_BOOT_COMPLETED.equals(intent.getAction())){UploadJob.schedule(c);UploadJob.retry(c);}
    }
}
