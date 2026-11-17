package org.residuelab.matomo;
import android.app.Activity;import android.os.Bundle;import android.widget.TextView;
public class Main extends Activity {public void onCreate(Bundle b){super.onCreate(b);TextView t=new TextView(this);t.setText("Matomo test embedding: withdrawal invalidates queued analytics events. Re-grant permits only new events.");setContentView(t);}}
