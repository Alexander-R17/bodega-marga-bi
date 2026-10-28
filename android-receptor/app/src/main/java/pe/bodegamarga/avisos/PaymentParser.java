package pe.bodegamarga.avisos;

import java.math.BigDecimal;
import java.text.Normalizer;
import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Reconoce avisos de recepción; nunca afirma que el banco haya verificado un pago. */
public final class PaymentParser {
    public static final String PACKAGE="com.bcp.innovacxion.yapeapp";
    private static final Pattern INCOMING=Pattern.compile("\\b(te yapeo|has recibido un yape|recibiste un yape|te envio un yape)\\b");
    private static final Pattern MONEY=Pattern.compile("(?i)S/\\.?[\\s\\p{Z}]*([0-9]+(?:[.,][0-9]{1,2})?)(?![0-9]|[.,][0-9]|[eE])");
    private static final Pattern REJECT=Pattern.compile("\\b(yapeaste|enviaste|pagaste|pendiente|solicitud|rechazad[oa]|cancelad[oa]|reversad[oa]|devuelt[oa]|contrasena|iniciar sesion|codigo de acceso|otp)\\b");
    public static Integer parse(String pkg,String title,String text) {
        if(!PACKAGE.equals(pkg))return null;
        String raw=(title==null?"":title)+" "+(text==null?"":text);
        if(raw.length()>2000)return null;
        String normalized=Normalizer.normalize(raw,Normalizer.Form.NFD).replaceAll("\\p{M}","").toLowerCase(Locale.ROOT);
        boolean newFormat=Normalizer.normalize(title==null?"":title,Normalizer.Form.NFD).replaceAll("\\p{M}","").trim().equalsIgnoreCase("Confirmacion de Pago")&&normalized.contains("te envio un pago por");
        if((!INCOMING.matcher(normalized).find()&&!newFormat)||REJECT.matcher(normalized).find())return null;
        Matcher markers=Pattern.compile("(?i)S/").matcher(raw);if(!markers.find()||markers.find())return null;
        Matcher matcher=MONEY.matcher(raw);
        if(!matcher.find())return null;
        String number=matcher.group(1);if(matcher.find())return null;
        try {int cents=new BigDecimal(number.replace(',','.')).movePointRight(2).intValueExact();return cents>0&&cents<=10000000?cents:null;}
        catch(ArithmeticException|NumberFormatException error){return null;}
    }
    private PaymentParser(){}
}
