package org.residuelab;

import android.content.Context;
import android.os.PersistableBundle;
import androidx.work.Constraints;
import androidx.work.Data;
import androidx.work.ExistingWorkPolicy;
import androidx.work.NetworkType;
import androidx.work.OneTimeWorkRequest;
import androidx.work.WorkInfo;
import androidx.work.WorkManager;
import java.util.List;
import java.util.concurrent.TimeUnit;

/** WorkManager substrate: persisted unique work per (tenant, kind); WorkManager reschedules it itself. */
public final class WorkBridge {
    static String name(int id) { return "rl-" + id; }
    public static Object enqueue(Context c, int id, long delay, PersistableBundle e) {
        Data.Builder d = new Data.Builder();
        if (e != null) for (String k : e.keySet()) {
            Object o = e.get(k);
            if (o instanceof Integer) d.putInt(k, (Integer) o); else if (o != null) d.putString(k, o.toString());
        }
        OneTimeWorkRequest r = new OneTimeWorkRequest.Builder(UpWorker.class)
                .setInitialDelay(delay, TimeUnit.MILLISECONDS)
                .setConstraints(new Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
                .setInputData(d.build()).addTag("rl").build();
        WorkManager.getInstance(c).enqueueUniqueWork(name(id), ExistingWorkPolicy.REPLACE, r);
        return Boolean.TRUE;
    }
    public static Object pending(Context c, int id, long delay, PersistableBundle e) {
        try {
            List<WorkInfo> l = WorkManager.getInstance(c).getWorkInfosForUniqueWork(name(id)).get();
            for (WorkInfo w : l) if (!w.getState().isFinished()) return Boolean.TRUE;
        } catch (Exception x) { }
        return Boolean.FALSE;
    }
    public static Object cancel(Context c, int id, long delay, PersistableBundle e) {
        WorkManager.getInstance(c).cancelUniqueWork(name(id));
        return Boolean.TRUE;
    }
}
