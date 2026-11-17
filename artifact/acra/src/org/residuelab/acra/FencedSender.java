package org.residuelab.acra;
import android.content.Context;
import org.acra.data.CrashReportData;
import org.acra.sender.ReportSender;
import org.acra.sender.ReportSenderException;
import org.json.JSONObject;
import java.nio.charset.StandardCharsets;
import java.util.UUID;
import org.residuelab.transport.HttpTransport;
/** ACRA retries retain the report's original source epoch; normal return retires a blocked report. */
public class FencedSender implements ReportSender {
    @Override public void send(Context c,CrashReportData data)throws ReportSenderException {
        try {
            String json=data.toJSON();JSONObject cd=new JSONObject(json).optJSONObject("CUSTOM_DATA");
            String label=cd==null?"":cd.optString("rd_label","");
            int parsed=-1;try {if(label.matches("crash:[0-9]+"))parsed=Integer.parseInt(label.substring(6));}catch(NumberFormatException ignored){}
            final int source=parsed;
            final String id=UUID.randomUUID().toString(),tag=cd==null?"missing":cd.optString("rd_tag","missing");
            if(source<0) {Fence.log(c,"BLOCK reason=missing_or_malformed_label tag="+tag);return;}
            HttpTransport.post("10.0.2.2",8789,"/ingest/crash",json.getBytes(StandardCharsets.UTF_8),Fence.lockFile(c),
                () -> {int[] s=Fence.read(c);return s[0]>=0&&s[1]==1&&source==s[0];},true,
                (kind,detail)->Fence.log(c,kind+" tag="+tag+" label="+label+" "+detail),id,1);
        } catch(HttpTransport.Denied e) {Fence.log(c,"REPORT_RETIRED policy_denied");}
        catch(Exception e) {throw new ReportSenderException("audited HTTP send failed; original label retained",e);}
    }
}
