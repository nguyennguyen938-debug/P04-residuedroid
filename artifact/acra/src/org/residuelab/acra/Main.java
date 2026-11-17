package org.residuelab.acra;
import android.app.Activity;
import android.os.Bundle;
import android.widget.*;
import java.util.ArrayList;
public class Main extends Activity {
    @Override protected void onCreate(Bundle b) {
        super.onCreate(b);LinearLayout layout=new LinearLayout(this);layout.setOrientation(LinearLayout.VERTICAL);layout.setPadding(24,24,24,24);
        TextView contract=new TextView(this);contract.setText("AcraLab test embedding\nTurning reporting off invalidates queued crash reports. Previously handed-off bytes may still arrive. Turning it on permits new reports; it does not revive old reports.");layout.addView(contract);
        TextView state=new TextView(this);state.setText("Policy: "+(Fence.read(this)[1]==1?"enabled":"disabled or unavailable"));layout.addView(state);
        ArrayList<Button> controls=new ArrayList<>();
        for(boolean enable:new boolean[]{false,true}) {Button button=new Button(this);button.setText(enable?"Enable new reports":"Disable and withdraw queued reports");layout.addView(button);controls.add(button);
            button.setOnClickListener(v->{for(Button control:controls)control.setEnabled(false);state.setText("Pending acknowledgement…");new Thread(()->{
                String result;try {Fence.setEnabled(this,enable);result=enable?"Enabled; old reports remain invalid":"Withdrawal acknowledged";}
                catch(Exception e){result="Not acknowledged: "+e.getMessage();}final String text=result;runOnUiThread(()->{state.setText(text);for(Button control:controls)control.setEnabled(true);});}).start();});}
        setContentView(layout);
    }
}
