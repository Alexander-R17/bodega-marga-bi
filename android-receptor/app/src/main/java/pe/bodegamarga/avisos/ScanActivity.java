package pe.bodegamarga.avisos;
import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.ImageFormat;
import android.hardware.Camera;
import android.os.Bundle;
import android.view.*;
import android.widget.*;
import java.util.Arrays;
import java.util.concurrent.Executors;
import java.util.concurrent.ExecutorService;
@SuppressWarnings("deprecation")
public final class ScanActivity extends Activity implements SurfaceHolder.Callback {
 private Camera camera;private SurfaceView preview;private TextView status;private boolean ready,foreground,busy,done;private long last;
 private final ExecutorService worker=Executors.newSingleThreadExecutor();private final CodeDecoder decoder=new CodeDecoder();
 @Override public void onCreate(Bundle state){super.onCreate(state);getWindow().getDecorView().setSystemUiVisibility(0);getWindow().setStatusBarColor(NativeUi.INK);NativeUi ui=new NativeUi(this);LinearLayout root=ui.column();root.setBackgroundColor(NativeUi.INK);ui.pad(root,20,24);
  TextView title=ui.text("Escanear producto",26,Color.WHITE,true);root.addView(title);status=ui.text("Centra el código de barras o QR. No se envían fotografías.",14,Color.rgb(211,225,211),false);ui.space(root,10);root.addView(status);ui.space(root,18);
  preview=new SurfaceView(this);root.addView(preview,new LinearLayout.LayoutParams(-1,0,1));preview.getHolder().addCallback(this);ui.addButton(root,"Volver",false,this::finish);setContentView(root);
  root.setOnApplyWindowInsetsListener((v,insets)->{if(android.os.Build.VERSION.SDK_INT>=30){android.graphics.Insets b=insets.getInsets(WindowInsets.Type.systemBars());v.setPadding(ui.dp(20),b.top+ui.dp(18),ui.dp(20),b.bottom+ui.dp(14));}return insets;});
  if(checkSelfPermission(Manifest.permission.CAMERA)!=PackageManager.PERMISSION_GRANTED)requestPermissions(new String[]{Manifest.permission.CAMERA},20);
 }
 @Override public void onRequestPermissionsResult(int n,String[] p,int[] r){super.onRequestPermissionsResult(n,p,r);if(n==20&&r.length>0&&r[0]==PackageManager.PERMISSION_GRANTED)open();else status.setText("Permite la cámara en Ajustes para escanear. Puedes registrar productos manualmente.");}
 void release(){if(camera!=null){try{camera.setPreviewCallback(null);camera.stopPreview();}catch(Exception ignored){}camera.release();camera=null;}}
 void open(){if(!ready||camera!=null||checkSelfPermission(Manifest.permission.CAMERA)!=PackageManager.PERMISSION_GRANTED)return;
  try{int chosen=0;Camera.CameraInfo info=new Camera.CameraInfo();for(int i=0;i<Camera.getNumberOfCameras();i++){Camera.getCameraInfo(i,info);if(info.facing==Camera.CameraInfo.CAMERA_FACING_BACK){chosen=i;break;}}
   camera=Camera.open(chosen);Camera.Parameters p=camera.getParameters();Camera.Size size=null;
   for(Camera.Size s:p.getSupportedPreviewSizes())if(s.width<=1280&&s.height<=960&&(size==null||s.width*s.height>size.width*size.height))size=s;
   if(size!=null)p.setPreviewSize(size.width,size.height);p.setPreviewFormat(ImageFormat.NV21);if(p.getSupportedFocusModes().contains(Camera.Parameters.FOCUS_MODE_CONTINUOUS_PICTURE))p.setFocusMode(Camera.Parameters.FOCUS_MODE_CONTINUOUS_PICTURE);
   camera.setParameters(p);Camera.getCameraInfo(chosen,info);camera.setDisplayOrientation(info.orientation);camera.setPreviewDisplay(preview.getHolder());
   camera.setPreviewCallback((bytes,c)->{if(done||busy||!foreground||System.currentTimeMillis()-last<250||worker.isShutdown())return;busy=true;last=System.currentTimeMillis();Camera.Size s=c.getParameters().getPreviewSize();byte[] y=Arrays.copyOf(bytes,s.width*s.height);
    worker.execute(()->{String code=null;try{code=decoder.decode(y,s.width,s.height);}catch(RuntimeException ignored){}final String value=code;runOnUiThread(()->{busy=false;if(!done&&foreground&&value!=null&&!isFinishing()){done=true;preview.performHapticFeedback(HapticFeedbackConstants.CONFIRM);setResult(RESULT_OK,new Intent().putExtra("code",value));finish();}});});
   });camera.startPreview();
  }catch(Exception e){release();status.setText("No se pudo abrir la cámara. Cierra otras apps que la estén usando y vuelve a intentarlo.");}
 }
 @Override protected void onResume(){super.onResume();foreground=true;if(ready)open();}
 @Override protected void onPause(){foreground=false;release();super.onPause();}
 @Override protected void onDestroy(){release();worker.shutdown();super.onDestroy();}
 @Override public void surfaceCreated(SurfaceHolder h){ready=true;open();}public void surfaceChanged(SurfaceHolder h,int f,int w,int x){}public void surfaceDestroyed(SurfaceHolder h){ready=false;release();}
}
