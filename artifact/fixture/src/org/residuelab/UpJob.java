package org.residuelab;

import android.app.job.JobParameters;
import android.app.job.JobService;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/** JobScheduler entry point. onStopJob is honoured cooperatively between batches (not mid-request). */
public class UpJob extends JobService {
    static final Map<Integer, Boolean> STOP = new ConcurrentHashMap<>();
    @Override public boolean onStartJob(final JobParameters p) {
        final int id = p.getJobId();
        STOP.put(id, false);
        new Thread(() -> {
            boolean again = false;
            try {
                again = Work.run(getApplicationContext(), p.getExtras().getInt("tenant"), p.getExtras().getInt("kind"),
                        p.getExtras(), () -> Boolean.TRUE.equals(STOP.get(id)));
            } catch (Throwable e) {
                Db.get(getApplicationContext()).event(p.getExtras().getInt("tenant"), "JOB_CRASH", e.toString());
            }
            jobFinished(p, again);
        }).start();
        return true;
    }
    @Override public boolean onStopJob(JobParameters p) {
        STOP.put(p.getJobId(), true);
        Db.get(getApplicationContext()).event(p.getExtras().getInt("tenant"), "ONSTOP", "job=" + p.getJobId() + ";reason=" + p.getStopReason());
        return false;
    }
}
