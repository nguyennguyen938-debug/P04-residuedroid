package org.residuelab;

import android.content.Context;
import android.os.PersistableBundle;

import androidx.work.Data;
import androidx.work.Worker;
import androidx.work.WorkerParameters;

public class UpWorker extends Worker {
    public UpWorker(Context c, WorkerParameters p) { super(c, p); }
    @Override public Result doWork() {
        Data d = getInputData();
        PersistableBundle e = new PersistableBundle();
        for (String k : d.getKeyValueMap().keySet()) {
            Object o = d.getKeyValueMap().get(k);
            if (o instanceof Integer) e.putInt(k, (Integer) o); else if (o != null) e.putString(k, o.toString());
        }
        boolean again = Work.run(getApplicationContext(), e.getInt("tenant"), e.getInt("kind"), e, this::isStopped);
        return again ? Result.retry() : Result.success();
    }
}
