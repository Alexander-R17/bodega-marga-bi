package pe.bodegamarga.avisos;
import com.google.zxing.*;import com.google.zxing.common.BitMatrix;import java.util.Arrays;
public final class NativeDecoderTest {
 static int count;
 static void roundtrip(String value,BarcodeFormat format,boolean rotate)throws Exception{
  BitMatrix m=new MultiFormatWriter().encode(value,format,640,480);int w=m.getWidth(),h=m.getHeight();byte[] y=new byte[w*h];
  for(int row=0;row<h;row++)for(int col=0;col<w;col++)y[row*w+col]=(byte)(m.get(col,row)?0:255);
  if(rotate){byte[] r=new byte[w*h];for(int row=0;row<h;row++)for(int col=0;col<w;col++)r[col*h+h-row-1]=y[row*w+col];y=r;int swap=w;w=h;h=swap;}
  if(!value.equals(new CodeDecoder().decode(y,w,h)))throw new AssertionError(format+" sin reconocer");count++;
 }
 static void notice(String title,String text,Integer expected){Integer actual=PaymentParser.parse(PaymentParser.PACKAGE,title,text);if(!java.util.Objects.equals(actual,expected))throw new AssertionError("Aviso incorrecto: "+actual+" / "+expected);count++;}
 public static void main(String[] args)throws Exception{
  for(boolean rotated:new boolean[]{false,true}){
   roundtrip("5901234123457",BarcodeFormat.EAN_13,rotated);roundtrip("96385074",BarcodeFormat.EAN_8,rotated);roundtrip("PAPA-1KG",BarcodeFormat.CODE_128,rotated);roundtrip("MARGA-001",BarcodeFormat.QR_CODE,rotated);roundtrip("https://marca.invalid/producto",BarcodeFormat.QR_CODE,rotated);
  }
  byte[] blank=new byte[640*480];Arrays.fill(blank,(byte)255);if(new CodeDecoder().decode(blank,640,480)!=null)throw new AssertionError();count++;
  for(String value:new String[]{"1.8","1.80","1,8","1,80"})notice("Confirmación de Pago","Persona sintética te envió un pago por S/ "+value+". El cód. de seguridad es: 000",180);
  notice("Confirmación de Pago","Persona sintética te envió un pago por S/\u00a04.20. El cód. de seguridad es: 000",420);
  for(String invalid:new String[]{"1.234","1,000.00","1e3","-1.80","0"})notice("Confirmación de Pago","Persona sintética te envió un pago por S/ "+invalid,null);
  notice("General","Persona sintética te envió un pago por S/ 4.20",null);
  notice("Confirmación de Pago","Persona sintética te envió un pago por S/ 4.20. Operación pendiente",null);
  System.out.println("Native decoder y Yape: "+count+" comprobaciones sintéticas correctas; no prueba física de cámara.");
 }
}
