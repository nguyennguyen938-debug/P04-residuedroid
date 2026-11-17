package org.residuelab;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

public class Boot extends BroadcastReceiver {
    @Override public void onReceive(Context c, Intent i) {
        Db.get(c).event(0, "BOOT_COMPLETED", "");
        // App.onCreate already ran the startup flush path; nothing else to do.
    }
}
