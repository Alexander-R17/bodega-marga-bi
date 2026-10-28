package pe.bodegamarga.avisos;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Color;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.Editable;
import android.text.TextWatcher;
import android.text.InputFilter;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.view.WindowInsets;
import android.widget.*;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.InputStream;
import java.io.ByteArrayOutputStream;
import java.math.BigDecimal;
import java.net.URL;
import javax.net.ssl.HttpsURLConnection;
import java.util.ArrayList;
import java.util.Locale;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Interfaz Android nativa. No contiene WebView ni abre el sistema en un navegador. */
public final class MainActivity extends Activity {
 private NativeUi ui;private MobileApi api;private LinearLayout root,body,navigation,list;private TextView syncStatus,notice;
 private JSONObject profile,cart=new JSONObject(),pending;private JSONArray products=new JSONArray();
 private final ExecutorService network=Executors.newSingleThreadExecutor(),pictures=Executors.newFixedThreadPool(2);
 private final Handler handler=new Handler(Looper.getMainLooper());private boolean foreground,busy,editing,cartLoading,catalogLoading;private int tab,page,generation;
 private String query="",alternateCode="";private long catalogRevision=-1;private EditText editingCode;
 private final android.util.LruCache<String,Bitmap> images=new android.util.LruCache<String,Bitmap>(12*1024*1024){protected int sizeOf(String k,Bitmap b){return b.getByteCount();}};
 interface Task{JSONObject run()throws Exception;}interface Done{void run(JSONObject value)throws Exception;}
 private String str(JSONObject o,String key){return o.optString(key,"");}
 private int dp(float x){return ui.dp(x);}private void toast(String s){Toast.makeText(this,s,Toast.LENGTH_LONG).show();}
 private boolean admin(){return profile!=null&&"administrador".equals(profile.optString("rol"));}
 private boolean seller(){return profile!=null&&!"analista".equals(profile.optString("rol"));}
 private String money(double n){return String.format(Locale.US,"S/ %.2f",n);}
 private boolean alive(){return !isFinishing()&&!isDestroyed();}
 @Override public void onCreate(Bundle state){
  super.onCreate(state);ui=new NativeUi(this);api=new MobileApi(this);buildRoot();
  try{if(!AuthStore.load(this).isEmpty()){loading("Conectando tu cuenta…");read(()->{api.bootstrap();return api.call("perfil",new JSONObject());},this::signedIn);return;}}catch(Exception ignored){}
  loginScreen();
 }
 private void buildRoot(){
  root=ui.column();root.setBackgroundColor(NativeUi.BG);setContentView(root);
  root.setOnApplyWindowInsetsListener((v,insets)->{if(android.os.Build.VERSION.SDK_INT>=30){android.graphics.Insets b=insets.getInsets(WindowInsets.Type.systemBars());v.setPadding(b.left,b.top,b.right,b.bottom);}else v.setPadding(insets.getSystemWindowInsetLeft(),insets.getSystemWindowInsetTop(),insets.getSystemWindowInsetRight(),insets.getSystemWindowInsetBottom());return insets;});
 }
 private void read(Task task,Done done){read(task,done,()->{});}
 private void read(Task task,Done done,Runnable complete){
  network.execute(()->{JSONObject value=null;Exception error=null;try{value=task.run();}catch(Exception e){error=e;}
   final JSONObject result=value;final Exception problem=error;handler.post(()->{if(!alive())return;complete.run();
    if(problem!=null){failed(problem);return;}try{done.run(result);}catch(Exception e){toast("No se pudo mostrar el resultado. Actualiza los datos.");}
   });
  });
 }
 private void failed(Exception e){
  String message=e instanceof MobileApi.Failure?e.getMessage():"No se recibió confirmación. Revisa la conexión.";
  if(syncStatus!=null)syncStatus.setText("Sin conexión reciente");
  if(e instanceof MobileApi.Failure&&(((MobileApi.Failure)e).status==401||((MobileApi.Failure)e).status==403)){api.logout();loginScreen();toast(message);return;}
  if(profile==null){loginScreen();toast(message);}else toast(message);
 }
 private void loading(String text){root.removeAllViews();LinearLayout c=ui.column();ui.pad(c,28,44);root.addView(c);ui.label(c,"BODEGA MARGA",20,true);ui.space(c,24);c.addView(new ProgressBar(this));ui.label(c,text,16,false);}
 private void loginScreen(){
  profile=null;busy=false;editing=false;root.removeAllViews();ScrollView sc=new ScrollView(this);LinearLayout c=ui.column();ui.pad(c,26,34);sc.addView(c);root.addView(sc,new LinearLayout.LayoutParams(-1,-1));
  TextView mark=ui.text("M",42,Color.WHITE,true);mark.setGravity(Gravity.CENTER);mark.setBackground(ui.shape(NativeUi.INK,22));c.addView(mark,new LinearLayout.LayoutParams(dp(76),dp(76)));
  ui.space(c,22);ui.label(c,"BODEGA MARGA",13,true);ui.space(c,10);ui.label(c,"Tu tienda,\na mano.",34,true);
  TextView intro=ui.text("Productos, existencias y carrito en una sola cuenta.",16,NativeUi.MUTED,false);ui.space(c,12);c.addView(intro);
  LinearLayout panel=ui.card(c);ui.label(panel,"Inicia sesión",21,true);
  EditText email=ui.field(panel,"Correo de tu cuenta", "",InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_EMAIL_ADDRESS);
  EditText password=ui.field(panel,"Contraseña", "",InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_PASSWORD);
  Button enter=ui.button("Ingresar a mi tienda",true,()->{
   if(email.getText().toString().trim().isEmpty()||password.getText().length()==0){toast("Completa correo y contraseña.");return;}
   if(busy)return;busy=true;String e=email.getText().toString(),p=password.getText().toString();password.setText("");loading("Validando tu acceso…");
   read(()->api.login(e,p),this::signedIn);
  });ui.space(panel,18);panel.addView(enter,new LinearLayout.LayoutParams(-1,dp(50)));
  ui.space(c,18);TextView info=ui.text("Usa el mismo correo y contraseña de la web. Tu rol y el correo verificado se comprueban en el servidor.",12,NativeUi.MUTED,false);c.addView(info);
  ui.addButton(c,"Configurar tienda",false,this::configure);
  ui.addButton(c,"Controles del receptor Yape",false,()->startActivity(new Intent(this,ReceiverActivity.class)));
  ui.space(c,12);ui.label(c,"APP NATIVA · 0.5",11,false);
 }
 private void configure(){
  LinearLayout c=ui.column();ui.pad(c,20,10);EditText e=ui.field(c,"Dirección de la función tienda-movil",api.endpoint,InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_URI);
  ui.label(c,"Copia la dirección mostrada en Actividad → Activar app nativa. No ingreses claves privadas.",12,false);
  new AlertDialog.Builder(this).setTitle("Conectar tu tienda").setView(c).setPositiveButton("Guardar",(d,w)->{
   loading("Comprobando tienda…");read(()->{api.configure(e.getText().toString());return new JSONObject();},v->{loginScreen();toast("Tienda configurada. Inicia sesión.");});
  }).setNeutralButton("Importar archivo",(d,w)->startActivityForResult(new Intent(Intent.ACTION_OPEN_DOCUMENT).setType("*/*").addCategory(Intent.CATEGORY_OPENABLE),303)).setNegativeButton("Cancelar",null).show();
 }
 private void signedIn(JSONObject p)throws Exception{
  profile=p;busy=false;cart=new JSONObject();products=new JSONArray();catalogRevision=-1;String saved=getSharedPreferences("native_shop",0).getString("pending","");pending=null;
  if(!saved.isEmpty()){JSONObject o=new JSONObject(saved);if(o.optString("uid").equals(profile.getString("uid"))&&o.optString("endpoint").equals(api.endpoint))pending=o;}
  tab=0;query="";home();loadCart(false);loadProducts(false);
 }
 private void home(){
  editing=false;editingCode=null;generation++;root.removeAllViews();
  LinearLayout header=ui.row();ui.pad(header,20,16);TextView mark=ui.text("M",25,Color.WHITE,true);mark.setGravity(Gravity.CENTER);mark.setBackground(ui.shape(NativeUi.INK,12));header.addView(mark,new LinearLayout.LayoutParams(dp(42),dp(42)));
  LinearLayout brand=ui.column();ui.pad(brand,10,0);ui.label(brand,"BODEGA MARGA",14,true);brand.addView(ui.text("Tienda inteligente",11,NativeUi.MUTED,false));header.addView(brand,new LinearLayout.LayoutParams(0,-2,1));
  TextView role=ui.text(admin()?"Administración":seller()?"Caja":"Análisis",11,NativeUi.INK,true);role.setBackground(ui.shape(NativeUi.SAGE,10));ui.pad(role,10,7);header.addView(role);root.addView(header);
  ScrollView scroll=new ScrollView(this);scroll.setFillViewport(true);body=ui.column();ui.pad(body,20,8);scroll.addView(body);root.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
  syncStatus=ui.text("Conectado a tu tienda",11,NativeUi.MUTED,false);body.addView(syncStatus);notice=ui.text("",13,NativeUi.INK,false);body.addView(notice);
  if(pending!=null){LinearLayout warning=ui.card(body);warning.setBackground(ui.shape(NativeUi.PEACH,14));ui.label(warning,"Hay un cambio pendiente de confirmación",15,true);ui.label(warning,"Reintenta el mismo cambio antes de registrar otro. Conserva su identificador.",12,false);ui.addButton(warning,"Reintentar cambio pendiente",true,this::retryMutation);}
  if(tab==0||tab==2)catalogScreen();else if(tab==1)cartScreen();else profileScreen();
  navigation=ui.row();ui.pad(navigation,10,10);navigation.setBackgroundColor(Color.WHITE);root.addView(navigation);refreshNavigation();
 }
 private void refreshNavigation(){
  if(navigation==null)return;navigation.removeAllViews();String[] labels={"Tienda","Carrito","Inventario","Perfil"};
  int units=0;JSONArray a=cart.optJSONArray("items");if(a!=null)for(int i=0;i<a.length();i++)units+=a.optJSONObject(i).optInt("cantidad");
  if(units>0)labels[1]+=" · "+units;
  for(int i=0;i<labels.length;i++){final int index=i;TextView b=ui.text(labels[i],11,tab==i?NativeUi.INK:NativeUi.MUTED,tab==i);b.setGravity(Gravity.CENTER);b.setBackground(ui.shape(tab==i?NativeUi.SAGE:Color.WHITE,12));ui.pad(b,2,14);navigation.addView(b,new LinearLayout.LayoutParams(0,-2,1));b.setOnClickListener(v->{if(busy)return;tab=index;query="";page=0;home();if(tab==0||tab==2)loadProducts(false);if(tab==1)loadCart(true);});}
 }
 private void catalogScreen(){
  LinearLayout banner=ui.card(body);banner.setBackground(ui.shape(tab==0?NativeUi.PEACH:NativeUi.SAGE,16));ui.label(banner,tab==0?"Tu tienda, en orden.":"Inventario al día",25,true);ui.space(banner,7);banner.addView(ui.text(tab==0?"Elige tus productos o escanea su código.":"Consulta existencias y registra los movimientos reales.",13,NativeUi.MUTED,false));
  EditText search=ui.field(body,"Buscar por nombre o código",query,InputType.TYPE_CLASS_TEXT);search.setHint("Ej. leche, arroz, 775…");
  search.addTextChangedListener(new TextWatcher(){Runnable delayed;public void beforeTextChanged(CharSequence s,int a,int c,int f){}public void onTextChanged(CharSequence s,int start,int before,int count){query=s.toString();if(delayed!=null)handler.removeCallbacks(delayed);delayed=()->{if(!editing&&(tab==0||tab==2)){page=0;loadProducts(false);}};handler.postDelayed(delayed,450);}public void afterTextChanged(Editable e){}});
  LinearLayout actions=ui.row();ui.space(body,10);body.addView(actions);
  Button scan=ui.button("Escanear código",true,()->scan(false));actions.addView(scan,new LinearLayout.LayoutParams(0,dp(46),1));
  if(tab==2&&admin()){Button add=ui.button("＋ Producto",false,()->editProduct(new JSONObject(),""));LinearLayout.LayoutParams ap=new LinearLayout.LayoutParams(0,dp(46),1);ap.leftMargin=dp(8);actions.addView(add,ap);}
  list=ui.column();body.addView(list);renderProducts();
 }
 private void loadProducts(boolean append){
  if(profile==null||editing||catalogLoading)return;catalogLoading=true;final int g=generation,t=tab,p=append?page+1:0;final String q=query;
  read(()->api.call("catalogo",new JSONObject().put("busqueda",q).put("pagina",p)),r->{
   if(g!=generation||editing||t!=tab)return;if(!q.equals(query)){loadProducts(false);return;}
   JSONArray incoming=r.getJSONArray("productos");if(append){for(int i=0;i<incoming.length();i++)products.put(incoming.get(i));}else products=incoming;
   page=p;catalogRevision=r.optLong("catalogo_revision");renderProducts();syncStamp();
  },()->catalogLoading=false);
 }
 private void renderProducts(){
  if(list==null||editing||!(tab==0||tab==2))return;list.removeAllViews();
  if(products.length()==0){ui.space(list,22);ui.label(list,"No hay productos con esta búsqueda.",15,false);return;}
  if(tab==2){for(int i=0;i<products.length();i++){JSONObject p=products.optJSONObject(i);LinearLayout card=ui.card(list),row=ui.row();card.addView(row);row.addView(image(p,58),new LinearLayout.LayoutParams(dp(58),dp(58)));LinearLayout name=ui.column();ui.pad(name,12,0);ui.label(name,p.optString("nombre"),15,true);name.addView(ui.text(p.optString("codigo"),11,NativeUi.MUTED,false));name.addView(ui.text(p.optString("categoria")+" · "+money(p.optDouble("precio")),12,NativeUi.MUTED,false));row.addView(name,new LinearLayout.LayoutParams(0,-2,1));TextView stock=ui.text(String.valueOf(p.optInt("stock"))+"\nunidades",15,NativeUi.INK,true);stock.setGravity(Gravity.END);row.addView(stock);card.setOnClickListener(v->{if(admin())editProduct(p,"");else detail(p);});}}
  else{
   LinearLayout row=null;
   for(int i=0;i<products.length();i++){
    if(i%2==0){row=ui.row();row.setGravity(Gravity.TOP);list.addView(row,new LinearLayout.LayoutParams(-1,-2));}
    JSONObject p=products.optJSONObject(i);LinearLayout card=ui.column();card.setBackground(ui.shape(Color.WHITE,14));ui.pad(card,11,12);LinearLayout.LayoutParams cp=new LinearLayout.LayoutParams(0,-2,1);cp.topMargin=dp(12);if(i%2==0)cp.rightMargin=dp(8);row.addView(card,cp);
    card.addView(image(p,128),new LinearLayout.LayoutParams(-1,dp(128)));ui.space(card,10);card.addView(ui.text(p.optString("categoria").toUpperCase(Locale.ROOT),9,NativeUi.MUTED,true));
    TextView name=ui.text(p.optString("nombre"),14,NativeUi.INK,true);name.setMaxLines(2);name.setMinHeight(dp(39));card.addView(name);ui.label(card,money(p.optDouble("precio")),20,true);
    TextView stock=ui.text(p.optInt("stock")>0?p.optInt("stock")+" disponibles":"Sin existencias",11,NativeUi.MUTED,false);ui.space(card,4);card.addView(stock);ui.space(card,10);
    Button add=ui.button("Agregar ＋",true,()->add(p,1));add.setEnabled(seller()&&p.optBoolean("activo")&&p.optInt("stock")>0&&pending==null&&!"COBRANDO".equals(cart.optString("estado")));add.setAlpha(add.isEnabled()?1f:.4f);card.addView(add,new LinearLayout.LayoutParams(-1,dp(40)));card.setOnClickListener(v->detail(p));
   }
   if(products.length()%2==1){View empty=new View(this);row.addView(empty,new LinearLayout.LayoutParams(0,1,1));}
  }
  if(products.length()>0&&products.length()%40==0)ui.addButton(list,"Ver más productos",false,()->loadProducts(true));
 }
 private View image(JSONObject product,int height){
  FrameLayout frame=new FrameLayout(this);frame.setBackground(ui.shape(NativeUi.BG,12));TextView mark=ui.text("M",32,Color.rgb(177,193,178),false);mark.setGravity(Gravity.CENTER);frame.addView(mark,new FrameLayout.LayoutParams(-1,-1));
  String url=product.optString("imagen_url","");JSONArray urls=product.optJSONArray("imagenes_urls");if(urls!=null&&urls.length()>0)url=urls.optString(0,url);
  if(!url.startsWith("https://")||url.toLowerCase(Locale.ROOT).endsWith(".svg"))return frame;
  ImageView img=new ImageView(this);img.setContentDescription(product.optString("nombre","Producto"));img.setScaleType(ImageView.ScaleType.FIT_CENTER);ui.pad(img,5,5);frame.addView(img,new FrameLayout.LayoutParams(-1,-1));final String source=url;Bitmap saved=images.get(source);if(saved!=null){img.setImageBitmap(saved);return frame;}
  pictures.execute(()->{try{
   HttpsURLConnection c=(HttpsURLConnection)new URL(source).openConnection();c.setConnectTimeout(6000);c.setReadTimeout(6000);c.setInstanceFollowRedirects(false);
   byte[] bytes;try{if(c.getResponseCode()!=200)return;try(InputStream input=c.getInputStream()){ByteArrayOutputStream out=new ByteArrayOutputStream();byte[] b=new byte[4096];int n;while((n=input.read(b))!=-1){out.write(b,0,n);if(out.size()>2097152)return;}bytes=out.toByteArray();}}finally{c.disconnect();}
   BitmapFactory.Options opts=new BitmapFactory.Options();opts.inJustDecodeBounds=true;BitmapFactory.decodeByteArray(bytes,0,bytes.length,opts);if(opts.outWidth<1||opts.outHeight<1)return;
   opts.inSampleSize=1;while(opts.outWidth/opts.inSampleSize>800||opts.outHeight/opts.inSampleSize>800)opts.inSampleSize*=2;opts.inJustDecodeBounds=false;Bitmap bitmap=BitmapFactory.decodeByteArray(bytes,0,bytes.length,opts);
   if(bitmap!=null){images.put(source,bitmap);handler.post(()->{if(alive())img.setImageBitmap(bitmap);});}
  }catch(Exception ignored){}});return frame;
 }
 private void detail(JSONObject p){
  LinearLayout c=ui.column();ui.pad(c,22,16);c.addView(image(p,170),new LinearLayout.LayoutParams(-1,dp(170)));ui.space(c,12);ui.label(c,p.optString("nombre"),22,true);ui.label(c,money(p.optDouble("precio")),24,true);
  c.addView(ui.text("Código: "+p.optString("codigo")+"\n"+p.optString("categoria")+" · "+p.optString("presentacion")+"\n"+p.optInt("stock")+" unidades disponibles",13,NativeUi.MUTED,false));ui.space(c,10);ui.label(c,p.optString("descripcion"),14,false);
  NumberPicker qty=new NumberPicker(this);qty.setMinValue(1);qty.setMaxValue(Math.max(1,Math.min(999,p.optInt("stock"))));qty.setValue(1);c.addView(qty);
  AlertDialog dialog=new AlertDialog.Builder(this).setView(c).setNegativeButton("Cerrar",null).create();
  if(seller()&&p.optBoolean("activo")&&p.optInt("stock")>0)ui.addButton(c,"Agregar al carrito",true,()->{dialog.dismiss();add(p,qty.getValue());});dialog.show();
 }
 private void add(JSONObject p,int count){
  if(!seller())return;
  if("COBRANDO".equals(cart.optString("estado"))){toast("El carrito está en proceso de cobro en la caja web.");return;}
  try{JSONObject data=new JSONObject().put("producto_id",p.getLong("id")).put("cantidad",count);
   changeCart("AGREGAR",data,"Producto agregado al carrito");
  }catch(Exception e){toast("No se pudo preparar el producto.");}
 }
 private void changeCart(String action,JSONObject data,String message)throws Exception{
  if(pending!=null){toast("Resuelve el cambio pendiente primero.");return;}
  long revision=cart.optLong("revision",-1);if(revision<0){loadCart(true);toast("Actualiza el carrito antes de editarlo.");return;}
  JSONObject payload=new JSONObject().put("operacion",UUID.randomUUID().toString()).put("accion",action).put("datos",data).put("revision",revision);
  mutate("carrito_cambiar",payload,message);
 }
 private void loadCart(boolean redraw){
  if(!seller()||profile==null||cartLoading)return;cartLoading=true;
  read(()->api.call("carrito",new JSONObject()),r->{
   if(profile==null)return;boolean changed=cart.optLong("revision",-1)!=r.optLong("revision")||cart.optLong("catalogo_revision",-1)!=r.optLong("catalogo_revision");cart=r;refreshNavigation();
   long revision=r.optLong("catalogo_revision");if(catalogRevision>=0&&revision!=catalogRevision&&!editing&&(tab==0||tab==2))loadProducts(false);
   if(redraw&&changed&&!editing&&tab==1){home();}else if(changed&&!editing&&(tab==0||tab==2)){renderProducts();}syncStamp();
  },()->cartLoading=false);
 }
 private void cartScreen(){
  ui.space(body,14);ui.label(body,"Tu carrito",28,true);body.addView(ui.text("Compartido con la web de esta misma cuenta.",13,NativeUi.MUTED,false));
  if(!seller()){ui.label(body,"El carrito está disponible para caja y administración.",14,false);return;}
  if("COBRANDO".equals(cart.optString("estado"))){LinearLayout c=ui.card(body);c.setBackground(ui.shape(NativeUi.PEACH,14));ui.label(c,"Cobro en curso",18,true);ui.label(c,"La caja web está confirmando esta venta. No se puede modificar el carrito.",13,false);}
  JSONArray lines=cart.optJSONArray("lineas");double subtotal=0,discount=0;
  if(lines==null||lines.length()==0){ui.space(body,30);ui.label(body,"Aún no agregaste productos.",18,true);ui.addButton(body,"Explorar tienda",true,()->{tab=0;home();loadProducts(false);});return;}
  final boolean canEdit=pending==null&&"ABIERTO".equals(cart.optString("estado"));
  for(int i=0;i<lines.length();i++){
   JSONObject p=lines.optJSONObject(i);int qty=p.optInt("cantidad");subtotal+=p.optDouble("precio")*qty;discount+=p.optDouble("descuento");
   LinearLayout c=ui.card(body);ui.label(c,p.optString("nombre"),16,true);c.addView(ui.text(money(p.optDouble("precio"))+" por unidad · "+p.optInt("stock")+" disponibles",12,NativeUi.MUTED,false));ui.space(c,10);
   LinearLayout row=ui.row();c.addView(row);Button minus=ui.button("−",false,()->{try{changeCart("CANTIDAD",new JSONObject().put("producto_id",p.getLong("producto_id")).put("cantidad",qty-1),"Cantidad actualizada");}catch(Exception e){failed(e);}});
   row.addView(minus,new LinearLayout.LayoutParams(dp(44),dp(40)));TextView amount=ui.text(String.valueOf(qty),18,NativeUi.INK,true);amount.setGravity(Gravity.CENTER);row.addView(amount,new LinearLayout.LayoutParams(dp(46),dp(40)));
   Button plus=ui.button("＋",false,()->{try{changeCart("CANTIDAD",new JSONObject().put("producto_id",p.getLong("producto_id")).put("cantidad",qty+1),"Cantidad actualizada");}catch(Exception e){failed(e);}});row.addView(plus,new LinearLayout.LayoutParams(dp(44),dp(40)));minus.setEnabled(canEdit);plus.setEnabled(canEdit);
   TextView total=ui.text(money(qty*p.optDouble("precio")-p.optDouble("descuento")),17,NativeUi.INK,true);total.setGravity(Gravity.END);row.addView(total,new LinearLayout.LayoutParams(0,-2,1));
  }
  LinearLayout summary=ui.card(body);summary.setBackground(ui.shape(NativeUi.SAGE,14));ui.label(summary,"Total de la compra",14,false);ui.label(summary,money(subtotal-discount),30,true);ui.space(summary,8);ui.label(summary,"Finaliza el cobro en la caja web que ya utilizas. El carrito está disponible con tu misma cuenta.",13,false);
  ui.addButton(body,"Vaciar carrito",false,()->new AlertDialog.Builder(this).setMessage("¿Quitar todos los productos de este carrito compartido?").setPositiveButton("Vaciar",(d,w)->{try{changeCart("VACIAR",new JSONObject(),"Carrito vacío");}catch(Exception e){failed(e);}}).setNegativeButton("Cancelar",null).show());
 }
 private void profileScreen(){
  ui.space(body,14);ui.label(body,"Mi cuenta",28,true);LinearLayout c=ui.card(body);ui.label(c,profile.optString("nombre"),23,true);c.addView(ui.text(profile.optString("email"),14,NativeUi.MUTED,false));ui.space(c,10);ui.label(c,"Rol: "+profile.optString("rol"),14,false);ui.label(c,"Tu cuenta y tu tienda conectadas",12,false);
  LinearLayout info=ui.card(body);ui.label(info,"Tu tienda siempre conectada",18,true);ui.label(info,"Usa esta misma cuenta en la web para compartir el carrito. Cada empleado conserva su propio carrito. Las existencias son comunes a toda la bodega.",14,false);
  ui.addButton(body,"Actualizar datos",true,()->{loadCart(true);toast("Actualizando datos de la tienda…");});
  ui.addButton(body,"Controles del receptor Yape",false,()->startActivity(new Intent(this,ReceiverActivity.class)));
  ui.addButton(body,"Cerrar sesión",false,()->{if(pending!=null){toast("Confirma primero el cambio pendiente para no perder su seguimiento.");return;}api.logout();profile=null;cart=new JSONObject();loginScreen();});
  ui.space(body,18);ui.label(body,"Bodega Marga · app nativa 0.5",12,false);
 }
 private void editProduct(JSONObject p,String captured){
  if(!admin()){toast("Solo administración puede editar productos.");return;}if(pending!=null){toast("Resuelve el cambio pendiente primero.");return;}
  editing=true;generation++;root.removeAllViews();alternateCode=captured.length()>60?captured:"";
  LinearLayout bar=ui.row();ui.pad(bar,20,14);Button back=ui.button("← Inventario",false,this::discardForm);bar.addView(back);root.addView(bar);
  ScrollView scroll=new ScrollView(this);LinearLayout form=ui.column();ui.pad(form,20,12);scroll.addView(form);root.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
  ui.label(form,p.has("id")?"Editar producto":"Nuevo producto",28,true);form.addView(ui.text("Guarda su ficha y registra las existencias por separado.",13,NativeUi.MUTED,false));
  LinearLayout basic=ui.card(form);ui.label(basic,"Información del producto",18,true);
  String initial=p.optString("codigo",captured.isEmpty()?"INT-"+UUID.randomUUID().toString().substring(0,8).toUpperCase(Locale.ROOT):captured.length()<=60?captured:"");
  EditText code=ui.field(basic,"Código interno o de barras",initial,InputType.TYPE_CLASS_TEXT);code.setFilters(new InputFilter[]{new InputFilter.LengthFilter(60)});editingCode=code;
  ui.addButton(basic,"Capturar código con cámara",false,()->scan(true));
  EditText name=ui.field(basic,"Nombre",p.optString("nombre"),InputType.TYPE_CLASS_TEXT);name.setFilters(new InputFilter[]{new InputFilter.LengthFilter(120)});
  EditText category=ui.field(basic,"Categoría",p.optString("categoria","Abarrotes"),InputType.TYPE_CLASS_TEXT);
  EditText supplier=ui.field(basic,"Proveedor",p.optString("proveedor","Proveedor local"),InputType.TYPE_CLASS_TEXT);
  EditText brand=ui.field(basic,"Marca",p.optString("marca"),InputType.TYPE_CLASS_TEXT);
  EditText pack=ui.field(basic,"Presentación",p.optString("presentacion"),InputType.TYPE_CLASS_TEXT);
  LinearLayout pricing=ui.card(form);ui.label(pricing,"Precio y reposición",18,true);
  int decimal=InputType.TYPE_CLASS_NUMBER|InputType.TYPE_NUMBER_FLAG_DECIMAL;
  EditText price=ui.field(pricing,"Precio de venta S/",p.has("precio")?String.valueOf(p.optDouble("precio")):"",decimal);
  EditText cost=ui.field(pricing,"Costo S/",p.has("costo")?String.valueOf(p.optDouble("costo")):"",decimal);
  EditText minimum=ui.field(pricing,"Stock mínimo",String.valueOf(p.optInt("stock_minimo",5)),InputType.TYPE_CLASS_NUMBER);
  EditText lead=ui.field(pricing,"Plazo del proveedor (días)",String.valueOf(p.optInt("plazo_dias",2)),InputType.TYPE_CLASS_NUMBER);
  Switch active=new Switch(this);active.setText("Producto activo");active.setTextColor(NativeUi.INK);active.setChecked(p.optBoolean("activo",true));ui.space(pricing,14);pricing.addView(active);
  LinearLayout details=ui.card(form);ui.label(details,"Descripción e imágenes",18,true);
  EditText desc=ui.field(details,"Descripción",p.optString("descripcion"),InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_FLAG_MULTI_LINE);desc.setSingleLine(false);desc.setMinLines(3);desc.setFilters(new InputFilter[]{new InputFilter.LengthFilter(1500)});
  ArrayList<EditText> urls=new ArrayList<>();LinearLayout imageFields=ui.column();details.addView(imageFields);JSONArray old=p.optJSONArray("imagenes_urls");int count=old!=null&&old.length()>0?old.length():1;
  for(int i=0;i<count;i++)urls.add(ui.field(imageFields,"URL de imagen "+(i+1),old!=null?old.optString(i,p.optString("imagen_url")):p.optString("imagen_url"),InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_URI));
  ui.addButton(details,"Agregar otra URL de imagen",false,()->{if(urls.size()>=8){toast("Máximo ocho imágenes.");return;}urls.add(ui.field(imageFields,"URL de imagen "+(urls.size()+1),"",InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_URI));});
  if(!alternateCode.isEmpty())ui.label(details,"Se asociará también el QR capturado como código alternativo.",12,false);
  ui.addButton(form,"Guardar producto",true,()->{
   try{
    String sku=code.getText().toString().trim(),nm=name.getText().toString().trim();if(sku.isEmpty()||nm.isEmpty()||category.getText().toString().trim().isEmpty()||supplier.getText().toString().trim().isEmpty())throw new IllegalArgumentException("Completa código, nombre, categoría y proveedor.");
    JSONArray images=new JSONArray();for(EditText url:urls){String value=url.getText().toString().trim();if(!value.isEmpty()){if(!value.matches("https://[^\\s]+")||value.length()>2048)throw new IllegalArgumentException("Las imágenes requieren una URL HTTPS válida.");images.put(value);}}
    JSONObject product=new JSONObject().put("id",p.has("id")?p.get("id"):JSONObject.NULL).put("codigo",sku).put("nombre",nm).put("categoria",category.getText().toString().trim()).put("proveedor",supplier.getText().toString().trim())
     .put("precio",number(price)).put("costo",number(cost)).put("stock_minimo",integer(minimum,0,1000000)).put("plazo_dias",integer(lead,0,90)).put("activo",active.isChecked()).put("descripcion",desc.getText().toString().trim()).put("marca",brand.getText().toString().trim()).put("presentacion",pack.getText().toString().trim()).put("imagenes_urls",images).put("imagen_url",images.length()>0?images.getString(0):"");
    JSONObject payload=new JSONObject().put("operacion",UUID.randomUUID().toString()).put("producto",product).put("revision_producto",p.optLong("revision_movil",0)).put("codigo_alternativo",alternateCode);
    mutate("guardar_producto",payload,"Producto guardado. Registra una entrada para agregar stock.");
   }catch(Exception e){toast(e.getMessage()==null?"Revisa los campos del producto.":e.getMessage());}
  });
  if(p.has("id")){ui.addButton(form,"Registrar entrada o ajuste",false,()->movement(p));ui.label(form,"Stock actual: "+p.optInt("stock")+" unidades",13,false);}ui.space(form,22);
 }
 private BigDecimal number(EditText e){try{BigDecimal n=new BigDecimal(e.getText().toString().trim().replace(',','.'));if(n.signum()<0||n.scale()>2||n.compareTo(new BigDecimal("100000000"))>=0)throw new Exception();return n;}catch(Exception x){throw new IllegalArgumentException("Usa importes positivos con hasta dos decimales.");}}
 private int integer(EditText e,int min,int max){try{String s=e.getText().toString().trim();if(!s.matches("[0-9]+"))throw new Exception();int n=Integer.parseInt(s);if(n<min||n>max)throw new Exception();return n;}catch(Exception x){throw new IllegalArgumentException("Revisa las cantidades enteras y sus límites.");}}
 private void movement(JSONObject p){
  LinearLayout c=ui.column();ui.pad(c,20,10);ui.label(c,p.optString("nombre"),18,true);ui.label(c,"Stock actual: "+p.optInt("stock"),14,false);
  Spinner kind=new Spinner(this);kind.setAdapter(new ArrayAdapter<>(this,android.R.layout.simple_spinner_dropdown_item,new String[]{"ENTRADA","AJUSTE","MERMA"}));c.addView(kind);
  EditText qty=ui.field(c,"Unidades (AJUSTE: total contado)","1",InputType.TYPE_CLASS_NUMBER);
  EditText cost=ui.field(c,"Costo unitario de entrada S/",String.valueOf(p.optDouble("costo",0)),InputType.TYPE_CLASS_NUMBER|InputType.TYPE_NUMBER_FLAG_DECIMAL);
  EditText reason=ui.field(c,"Motivo o referencia","",InputType.TYPE_CLASS_TEXT);
  AlertDialog d=new AlertDialog.Builder(this).setTitle("Movimiento de inventario").setView(c).setNegativeButton("Cancelar",null).create();
  ui.addButton(c,"Registrar movimiento",true,()->{try{
   String type=kind.getSelectedItem().toString(),why=reason.getText().toString().trim();if(why.length()<3||why.length()>200)throw new IllegalArgumentException("Escribe un motivo de 3 a 200 caracteres.");
   JSONObject payload=new JSONObject().put("operacion",UUID.randomUUID().toString()).put("producto_id",p.getLong("id")).put("tipo",type).put("cantidad",integer(qty,type.equals("AJUSTE")?0:1,1000000)).put("costo",number(cost)).put("motivo",why);
   d.dismiss();mutate("movimiento",payload,"Existencias actualizadas en ambos dispositivos.");
  }catch(Exception e){toast(e.getMessage());}});d.show();
 }
 private void discardForm(){new AlertDialog.Builder(this).setMessage("¿Volver al inventario y descartar los cambios sin guardar?").setPositiveButton("Volver",(d,w)->{tab=2;home();loadProducts(false);}).setNegativeButton("Seguir editando",null).show();}
 private void mutate(String action,JSONObject payload,String message)throws Exception{
  if(pending!=null){toast("Reintenta el cambio pendiente antes de registrar otro.");return;}
  pending=new JSONObject().put("uid",profile.getString("uid")).put("endpoint",api.endpoint).put("action",action).put("payload",payload).put("message",message);
  getSharedPreferences("native_shop",0).edit().putString("pending",pending.toString()).commit();retryMutation();
 }
 private void retryMutation(){
  if(pending==null||busy)return;busy=true;JSONObject request=pending;
  if(notice!=null)notice.setText("Guardando cambio…");
  network.execute(()->{Exception error=null;try{api.call(request.getString("action"),request.getJSONObject("payload"));}catch(Exception e){error=e;}final Exception problem=error;
   handler.post(()->{busy=false;if(!alive())return;
    if(problem==null){String message=request.optString("message","Cambio guardado");clearPending();editing=false;tab=request.optString("action").equals("carrito_cambiar")?tab:2;home();toast(message);loadCart(tab==1);if(tab==0||tab==2)loadProducts(false);}
    else if(problem instanceof MobileApi.Failure&&((MobileApi.Failure)problem).confirmed){clearPending();failed(problem);if(profile!=null&&!editing){home();loadCart(tab==1);}}
    else{failed(problem);if(!editing)home();else new AlertDialog.Builder(this).setMessage("No hay confirmación. Reintenta este mismo cambio; no registres otro.").setPositiveButton("Reintentar",(d,w)->retryMutation()).setNegativeButton("Conservar pendiente",(d,w)->{tab=2;home();}).show();}
   });
  });
 }
 private void clearPending(){pending=null;getSharedPreferences("native_shop",0).edit().remove("pending").commit();}
 private void scan(boolean form){if(profile==null){toast("Inicia sesión primero.");return;}if(pending!=null){toast("Resuelve el cambio pendiente primero.");return;}startActivityForResult(new Intent(this,ScanActivity.class),form?302:301);}
 @Override protected void onActivityResult(int request,int result,Intent data){super.onActivityResult(request,result,data);if(result!=RESULT_OK||data==null)return;
  if(request==303&&data.getData()!=null){
   try(java.io.InputStream input=getContentResolver().openInputStream(data.getData())){
    if(input==null)throw new Exception();java.io.ByteArrayOutputStream out=new java.io.ByteArrayOutputStream();byte[] b=new byte[1024];int n;
    while((n=input.read(b))!=-1){out.write(b,0,n);if(out.size()>4096)throw new Exception();}
    String endpoint=new JSONObject(out.toString("UTF-8")).getString("endpoint");loading("Comprobando tienda…");
    read(()->{api.configure(endpoint);return new JSONObject();},v->{loginScreen();toast("Tienda configurada. Inicia sesión.");});
   }catch(Exception e){toast("Archivo de configuración inválido. Descarga tienda_marga_config.json desde la web.");}return;
  }
  String code=data.getStringExtra("code");if(code==null)return;
  if(request==302&&editingCode!=null){if(code.length()<=60)editingCode.setText(code);else{alternateCode=code;toast("QR capturado como código alternativo. Conserva un código interno corto.");}return;}
  if(request==301){final int target=tab;network.execute(()->{JSONObject product=null;Exception error=null;try{product=api.call("producto",new JSONObject().put("codigo",code));}catch(Exception e){error=e;}final JSONObject p=product;final Exception problem=error;
   handler.post(()->{if(!alive())return;if(problem==null){if(target==2&&admin())editProduct(p,"");else if(seller())add(p,1);else detail(p);}
    else if(target==2&&admin()&&problem.getMessage()!=null&&problem.getMessage().contains("Código no registrado"))new AlertDialog.Builder(this).setMessage("Este código aún no está en inventario. ¿Crear su ficha?").setPositiveButton("Crear producto",(d,w)->editProduct(new JSONObject(),code)).setNegativeButton("Cancelar",null).show();else failed(problem);
   });
  });}
 }
 private void syncStamp(){if(syncStatus!=null)syncStatus.setText("Actualizado · "+android.text.format.DateFormat.format("HH:mm:ss",System.currentTimeMillis()));}
 private final Runnable poll=new Runnable(){public void run(){if(!foreground)return;if(profile!=null&&!busy&&!editing){if(seller())loadCart(tab==1);else if(tab==0||tab==2)loadProducts(false);}handler.postDelayed(this,4000);}};
 @Override protected void onResume(){super.onResume();foreground=true;handler.removeCallbacks(poll);handler.postDelayed(poll,1500);
  android.content.ComponentName listener=new android.content.ComponentName(this,YapeListener.class);if(Config.enabled(this)&&((android.app.NotificationManager)getSystemService(NOTIFICATION_SERVICE)).isNotificationListenerAccessGranted(listener))android.service.notification.NotificationListenerService.requestRebind(listener);
 }
 @Override protected void onPause(){foreground=false;handler.removeCallbacks(poll);super.onPause();}
 @Override public void onBackPressed(){if(editing){discardForm();return;}if(profile!=null&&tab!=0){tab=0;home();loadProducts(false);}else super.onBackPressed();}
 @Override protected void onDestroy(){handler.removeCallbacks(poll);network.shutdownNow();pictures.shutdownNow();super.onDestroy();}
}
