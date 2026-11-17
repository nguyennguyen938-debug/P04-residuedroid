package org.residuelab;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.os.PersistableBundle;

/** AlarmManager substrate: alarms do not survive reboot/force-stop; the app re-arms them from its outbox. */
public class AlarmRx extends BroadcastReceiver {
    @Override public void onReceive(Context c, Intent i) {
        final PendingResult pr = goAsync();
        final Context ac = c.getApplicationContext();
        final int tenant = i.getIntExtra("tenant", 0), kind = i.getIntExtra("kind", 0);
        final PersistableBundle e = new PersistableBundle();
        for (String k : new String[]{"tag", "payload", "srcs", "labels"}) if (i.getStringExtra(k) != null) e.putString(k, i.getStringExtra(k));
        new Thread(() -> {
            try {
                boolean again = Work.run(ac, tenant, kind, e, null);
                if (again) Sched.enqueue(ac, Model.TENANTS[tenant], kind, 30_000, e, "alarm-retry");
            } catch (Throwable x) { Db.get(ac).event(tenant, "JOB_CRASH", x.toString()); }
            pr.finish();
        }).start();
    }
}
