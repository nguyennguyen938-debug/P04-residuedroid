package org.residuelab.acra;

import android.app.Application;
import android.app.job.JobInfo;
import android.content.Context;
import org.acra.ACRA;
import org.acra.config.CoreConfigurationBuilder;
import org.acra.config.HttpSenderConfigurationBuilder;
import org.acra.config.SchedulerConfigurationBuilder;
import org.acra.data.StringFormat;
import org.acra.sender.HttpSender;

/** Real ACRA 5.14.2 with its HttpSender (variant "acra") or a fenced ReportSender (variant "acrafence"),
 *  and the AdvancedSenderScheduler requiring network (a documented ACRA configuration). */
public class AcraApp extends Application {
    public static final String URI = "http://10.0.2.2:8789/ingest/crash";
    @Override protected void attachBaseContext(Context base) {
        super.attachBaseContext(base);
        try {Fence.initialize(this);} catch(Exception e) {Fence.log(this,"INITIALIZE_FAILED "+e);}
        CoreConfigurationBuilder b = new CoreConfigurationBuilder()
                .withReportFormat(StringFormat.JSON)
                .withReportContent(org.acra.ReportField.REPORT_ID, org.acra.ReportField.CUSTOM_DATA, org.acra.ReportField.STACK_TRACE)
                .withPluginConfigurations(
                        new HttpSenderConfigurationBuilder().withEnabled(true).withUri(URI)
                                .withHttpMethod(HttpSender.Method.POST).withConnectionTimeout(3000).build(),
                        new SchedulerConfigurationBuilder().withEnabled(true)
                                .withRequiresNetworkType(JobInfo.NETWORK_TYPE_ANY).build());
        ACRA.init(this, b);
    }
}
