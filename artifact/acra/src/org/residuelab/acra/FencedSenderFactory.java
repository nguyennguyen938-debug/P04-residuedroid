package org.residuelab.acra;

import android.content.Context;
import org.acra.config.CoreConfiguration;
import org.acra.sender.ReportSender;
import org.acra.sender.ReportSenderFactory;

public class FencedSenderFactory implements ReportSenderFactory {
    @Override public ReportSender create(Context c, CoreConfiguration cfg) { return new FencedSender(); }
}
