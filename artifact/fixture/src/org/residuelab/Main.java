package org.residuelab;

import android.app.Activity;
import android.os.Bundle;
import android.widget.TextView;

public class Main extends Activity {
    @Override protected void onCreate(Bundle b) {
        super.onCreate(b);
        TextView tv = new TextView(this);
        tv.setText("ResidueLab variant=" + Model.variant(this).name);
        setContentView(tv);
        Db.get(this).event(0, "UI_OPEN", "");
    }
}
