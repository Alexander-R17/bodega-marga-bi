package pe.bodegamarga.avisos;
import android.app.Activity;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.view.View;
import android.widget.*;
final class NativeUi {
 static final int BG=Color.rgb(248,247,242),INK=Color.rgb(24,59,49),MUTED=Color.rgb(108,123,115),LINE=Color.rgb(225,231,224),SAGE=Color.rgb(233,241,233),PEACH=Color.rgb(250,226,215);
 final Activity a;NativeUi(Activity a){this.a=a;}
 int dp(float x){return Math.round(x*a.getResources().getDisplayMetrics().density);}
 GradientDrawable shape(int color,int radius){GradientDrawable d=new GradientDrawable();d.setColor(color);d.setCornerRadius(dp(radius));return d;}
 LinearLayout column(){LinearLayout v=new LinearLayout(a);v.setOrientation(LinearLayout.VERTICAL);return v;}
 LinearLayout row(){LinearLayout v=new LinearLayout(a);v.setGravity(android.view.Gravity.CENTER_VERTICAL);return v;}
 void pad(View v,int x,int y){v.setPadding(dp(x),dp(y),dp(x),dp(y));}
 TextView text(String s,int size,int color,boolean bold){TextView t=new TextView(a);t.setText(s);t.setTextColor(color);t.setTextSize(size);t.setTypeface(Typeface.create(bold?"sans-serif-medium":"sans-serif",bold?Typeface.BOLD:Typeface.NORMAL));return t;}
 TextView label(LinearLayout root,String s,int size,boolean bold){TextView t=text(s,size,INK,bold);root.addView(t);return t;}
 void space(LinearLayout r,int h){r.addView(new View(a),new LinearLayout.LayoutParams(1,dp(h)));}
 Button button(String s,boolean primary,Runnable action){Button b=new Button(a);b.setText(s);b.setTextSize(14);b.setAllCaps(false);b.setTypeface(Typeface.create("sans-serif-medium",Typeface.NORMAL));b.setTextColor(primary?Color.WHITE:INK);b.setBackground(new android.graphics.drawable.RippleDrawable(android.content.res.ColorStateList.valueOf(primary?0x33ffffff:0x22173b32),shape(primary?INK:SAGE,12),null));b.setMinHeight(dp(46));pad(b,14,4);b.setOnClickListener(v->action.run());return b;}
 void addButton(LinearLayout root,String s,boolean primary,Runnable action){Button b=button(s,primary,action);LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,dp(48));p.topMargin=dp(10);root.addView(b,p);}
 LinearLayout card(LinearLayout root){LinearLayout c=column();c.setBackground(shape(Color.WHITE,16));c.setElevation(dp(1));pad(c,16,16);LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,-2);p.topMargin=dp(12);root.addView(c,p);return c;}
 EditText field(LinearLayout root,String label,String value,int type){space(root,12);TextView l=text(label,12,MUTED,true);root.addView(l);EditText e=new EditText(a);e.setSingleLine(true);e.setTextSize(15);e.setTextColor(INK);e.setText(value==null?"":value);e.setInputType(type);e.setBackground(shape(BG,10));pad(e,12,10);LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,dp(48));p.topMargin=dp(5);root.addView(e,p);return e;}
 void line(LinearLayout root){View l=new View(a);l.setBackgroundColor(LINE);LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,dp(1));p.topMargin=dp(12);p.bottomMargin=dp(12);root.addView(l,p);}
}
