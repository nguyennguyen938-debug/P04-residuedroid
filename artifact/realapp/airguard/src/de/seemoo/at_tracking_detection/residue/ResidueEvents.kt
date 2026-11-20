package de.seemoo.at_tracking_detection.residue

import android.content.Context
import android.os.SystemClock
import org.json.JSONObject
import java.io.File

/** P04 B2: append-only event log read by the harness (device clock only; never mixed with host time). */
object ResidueEvents {
    @Synchronized
    fun log(c: Context, kind: String, detail: String) {
        val o = JSONObject().put("kind", kind).put("detail", detail)
            .put("mono_ns", SystemClock.elapsedRealtimeNanos()).put("wall_ms", System.currentTimeMillis())
            .put("pid", android.os.Process.myPid())
        File(c.filesDir, "residue-events.jsonl").appendText(o.toString() + "\n")
    }
}
