package pe.bodegamarga.avisos;
import com.google.zxing.*;
import com.google.zxing.common.HybridBinarizer;
import java.util.*;
final class CodeDecoder {
 final MultiFormatReader reader=new MultiFormatReader();
 CodeDecoder(){Map<DecodeHintType,Object> hints=new EnumMap<>(DecodeHintType.class);hints.put(DecodeHintType.POSSIBLE_FORMATS,Arrays.asList(BarcodeFormat.QR_CODE,BarcodeFormat.EAN_13,BarcodeFormat.EAN_8,BarcodeFormat.UPC_A,BarcodeFormat.UPC_E,BarcodeFormat.CODE_128,BarcodeFormat.CODE_39,BarcodeFormat.ITF));hints.put(DecodeHintType.TRY_HARDER,true);reader.setHints(hints);}
 private String attempt(byte[] y,int w,int h){try{String result=reader.decodeWithState(new BinaryBitmap(new HybridBinarizer(new PlanarYUVLuminanceSource(y,w,h,0,0,w,h,false)))).getText().trim();if(result.isEmpty()||result.length()>512)return null;for(char c:result.toCharArray())if(Character.isISOControl(c))return null;return result;}catch(ReaderException e){return null;}finally{reader.reset();}}
 String decode(byte[] y,int w,int h){if(y==null||w<1||h<1||(long)w*h>y.length)return null;String value=attempt(y,w,h);if(value!=null)return value;byte[] rotated=new byte[w*h];for(int row=0;row<h;row++)for(int col=0;col<w;col++)rotated[col*h+h-row-1]=y[row*w+col];return attempt(rotated,h,w);}
}
