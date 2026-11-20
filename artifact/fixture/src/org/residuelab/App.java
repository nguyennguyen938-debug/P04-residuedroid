package org.residuelab;

import android.app.Application;

public class App extends Application {
    @Override public void onCreate() {
        super.onCreate();
        Db db = Db.get(this);
        try { Fence.PORT = Integer.parseInt(db.meta("sink_port", "8787")); } catch (Exception e) { }
        Fence.HOST = db.meta("sink_host", "10.0.2.2");
        db.event(0, "PROC_START", "variant=" + Model.variant(this).name);
        final android.content.Context c = this;
        new Thread(() -> { try { Sched.resurrect(c, "proc-start"); } catch (Throwable e) { Db.get(c).event(0, "RESURRECT_ERR", e.toString()); } }).start();
    }
}
