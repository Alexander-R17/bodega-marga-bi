package pe.bodegamarga.avisos;

public final class ParserTest {
    static int count;
    static void check(String pkg,String title,String text,Integer expected){
        Integer actual=PaymentParser.parse(pkg,title,text);
        if(!java.util.Objects.equals(actual,expected))throw new AssertionError("Resultado "+actual+", esperado "+expected+" en "+text);
        count++;
    }
    public static void main(String[] args){
        String p=PaymentParser.PACKAGE;
        check(p,"Yape","Ejemplo te yapeó S/ 10.50",1050);
        check(p,"Yape","Ejemplo te yapeó S/1",100);
        check(p,"Yape","Has recibido un yape de S/ 5,50",550);
        check(p,"Yape","Recibiste un yape S/ 0.10",10);
        check(p,"Yape","Ejemplo te yapeó S/ 10.00.",1000);
        check(p,"Yape","Ejemplo te yapeó S/. 2.50",250);
        check("com.fake.yape","Yape","Ejemplo te yapeó S/ 10.00",null);
        check(p,"Yape","Yapeaste S/ 10.00 a Ejemplo",null);
        check(p,"Yape","Tu código de acceso es 123456",null);
        check(p,"Yape","Ejemplo te yapeó S/ 10.00. Operación cancelada",null);
        check(p,"Yape","Ejemplo te yapeó S/ 0.00",null);
        check(p,"Yape","Ejemplo te yapeó S/ 1.234",null);
        check(p,"Yape","Ejemplo te yapeó S/ 1,000.00",null);
        check(p,"Yape","Ejemplo te yapeó S/ 10.00 y S/ 20.00",null);
        check(p,"Yape","Ejemplo te yapeó S/ 10.5",1050);
        check(p,"Yape","Ejemplo te yapeó S/ 99999999999999999999",null);
        check(p,"Yape","Recarga y gana S/ 20.00",null);
        check(p,"Yape",null,null);
        check(p,"Yape","Has recibido un yape S/ 100000.00",10000000);
        check(p,"Yape","Has recibido un yape S/ 100000.01",null);
        check(p,"Yape","x".repeat(2001),null);
        System.out.println("Parser: "+count+" comprobaciones correctas con textos sintéticos.");
    }
}
