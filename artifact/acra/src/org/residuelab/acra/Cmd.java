package org.residuelab.acra;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import org.acra.ACRA;

public class Cmd extends BroadcastReceiver {
    @Override public void onReceive(Context c0, Intent i) {
        final Context c = c0.getApplicationContext();
        String a = i.getAction() == null ? "" : i.getAction();
        try {
            switch (a) {
                case "rl.CRASH": {
                    final String tag = i.getStringExtra("tag");
                    int[] s = Fence.read(c);
                    if(s[0]<0||s[1]!=1){setResultData("collection disabled");break;}
                    ACRA.getErrorReporter().putCustomData("rd_tag", tag);
                    ACRA.getErrorReporter().putCustomData("rd_label", "crash:" + s[0]);
                    Fence.log(c, "CRASH tag=" + tag + " epoch=" + s[0]);
                    new Thread(() -> { throw new IllegalStateException("residue-crash " + tag); }).start();
                    setResultData("crashing");
                    break;
                }
                case "rl.DISABLE": {   // the in-app "send crash reports" toggle switched off
                    Fence.setEnabled(c, false);
                    setResultData("disabled");
                    break;
                }
                case "rl.TEST_SEND": {
                    final PendingResult pr=goAsync();final String label=i.getStringExtra("label"),tag=i.getStringExtra("tag");
                    new Thread(()->{try {
                        org.json.JSONObject custom=new org.json.JSONObject();custom.put("rd_tag",tag);
                        if(label!=null&&!label.equals("missing"))custom.put("rd_label",label);
                        org.acra.data.CrashReportData data=new org.acra.data.CrashReportData();data.put(org.acra.ReportField.CUSTOM_DATA,custom);
                        new FencedSender().send(c,data);pr.setResultData("sender returned");
                    }catch(Exception e){pr.setResultData("error "+e);}finally{pr.finish();}}).start();break;
                }
                case "rl.ENABLE": { Fence.setEnabled(c,true);setResultData("enabled");break; }
                case "rl.STATE": {
                    String[] ap = c.getDir("ACRA-approved", Context.MODE_PRIVATE).list();
                    String[] un = c.getDir("ACRA-unapproved", Context.MODE_PRIVATE).list();
                    setResultData("approved=" + (ap == null ? 0 : ap.length) + ";unapproved=" + (un == null ? 0 : un.length)
                            + ";pending_jobs=" + c.getSystemService(android.app.job.JobScheduler.class).getAllPendingJobs().size());
                    break;
                }
                default: setResultData("unknown");
            }
        } catch (Exception e) { setResultData("error " + e); }
    }
}
