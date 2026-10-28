package pe.bodegamarga.avisos;

import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;
import java.util.ArrayList;
import java.util.List;

final class QueueDb extends SQLiteOpenHelper {
    static final class Event {
        final String id,device;final int cents;final long time;
        Event(String id,String device,int cents,long time){this.id=id;this.device=device;this.cents=cents;this.time=time;}
    }
    QueueDb(Context c){super(c,"avisos.db",null,1);}
    @Override public void onCreate(SQLiteDatabase db){db.execSQL("CREATE TABLE queue(id TEXT PRIMARY KEY,device TEXT NOT NULL,cents INTEGER NOT NULL,ts INTEGER NOT NULL,state TEXT NOT NULL)");}
    @Override public void onUpgrade(SQLiteDatabase db,int oldVersion,int newVersion){}
    void add(Event e){
        SQLiteDatabase db=getWritableDatabase();
        db.delete("queue","ts<?",new String[]{Long.toString(System.currentTimeMillis()-7L*86400000)});
        try(Cursor c=db.rawQuery("SELECT id FROM queue WHERE id=?",new String[]{e.id})){if(c.moveToFirst())return;}
        try(Cursor c=db.rawQuery("SELECT count(*) FROM queue WHERE state='PENDING'",null)){
            if(c.moveToFirst()&&c.getInt(0)>=1000)throw new IllegalStateException("Cola llena");
        }
        ContentValues v=new ContentValues();v.put("id",e.id);v.put("device",e.device);v.put("cents",e.cents);v.put("ts",e.time);v.put("state","PENDING");
        db.insertOrThrow("queue",null,v);
    }
    List<Event> pending(String device){
        List<Event> rows=new ArrayList<>();
        try(Cursor c=getReadableDatabase().query("queue",new String[]{"id","cents","ts"},"device=? AND state='PENDING'",new String[]{device},null,null,"ts ASC","40")){
            while(c.moveToNext())rows.add(new Event(c.getString(0),device,c.getInt(1),c.getLong(2)));
        }
        return rows;
    }
    void mark(String id,String state){ContentValues v=new ContentValues();v.put("state",state);getWritableDatabase().update("queue",v,"id=?",new String[]{id});}
    String summary(){
        StringBuilder result=new StringBuilder();
        try(Cursor c=getReadableDatabase().rawQuery("SELECT state,count(*) FROM queue GROUP BY state",null)){
            while(c.moveToNext())result.append(c.getString(0)).append(": ").append(c.getInt(1)).append("\n");
        }
        return result.length()==0?"Todavía no hay avisos guardados.":result.toString();
    }
}
