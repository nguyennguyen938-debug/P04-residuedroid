package de.seemoo.at_tracking_detection.residue

import android.content.Context
import android.database.sqlite.SQLiteDatabase
import org.residuelab.transport.Coordinator
import java.io.File

/**
 * P04 B2: durable consent epochs for AirGuard's study-data sharing, keyed by collection time (no change to the app's Room
 * schema). intervals(epoch, granted_at, withdrawn_at). Withdrawal closes the open interval under the same coordinator lock
 * the fenced transport takes for every chunk, so a chunk check either precedes the withdrawal or sees it.
 * Label of an item = the epoch whose interval contains its timestamp; none -> forbidden.
 */
object ConsentLog {
    fun lock(c: Context) = File(c.filesDir, "residue-policy.lock")
    private fun db(c: Context): SQLiteDatabase = c.openOrCreateDatabase("residue_consent.db", Context.MODE_PRIVATE, null).also {
        it.execSQL("CREATE TABLE IF NOT EXISTS intervals(epoch INTEGER PRIMARY KEY, granted_at INTEGER NOT NULL, withdrawn_at INTEGER)")
    }
    private fun openEpoch(d: SQLiteDatabase): Long? =
        d.rawQuery("SELECT epoch FROM intervals WHERE withdrawn_at IS NULL", null).use { if (it.moveToFirst()) it.getLong(0) else null }

    fun grant(c: Context, now: Long = System.currentTimeMillis()) {
        ResidueEvents.log(c, "GRANT_REQUEST", "t=$now")
        Coordinator.call(lock(c), System.nanoTime() + 5_000_000_000L) {
            db(c).use { d -> if (openEpoch(d) == null) d.execSQL(
                "INSERT INTO intervals(epoch, granted_at) VALUES((SELECT IFNULL(MAX(epoch), 0) + 1 FROM intervals), ?)", arrayOf<Any>(now)) }
            null
        }
        ResidueEvents.log(c, "GRANT_ACK", "t=$now")
    }

    fun withdraw(c: Context, now: Long = System.currentTimeMillis()) {
        ResidueEvents.log(c, "WITHDRAW_REQUEST", "t=$now")
        Coordinator.call(lock(c), System.nanoTime() + 5_000_000_000L) {
            db(c).use { d -> d.execSQL("UPDATE intervals SET withdrawn_at = ? WHERE withdrawn_at IS NULL", arrayOf<Any>(now)) }
            null
        }
        ResidueEvents.log(c, "WITHDRAW_ACK", "t=$now")
    }

    /** True only if consent is open now and every timestamp lies inside the open interval. Called under the lock. */
    fun permitted(c: Context, timestampsMs: List<Long>): Boolean = db(c).use { d ->
        val e = openEpoch(d) ?: return@use false
        val start = d.rawQuery("SELECT granted_at FROM intervals WHERE epoch = ?", arrayOf(e.toString())).use { it.moveToFirst(); it.getLong(0) }
        timestampsMs.all { it >= start }
    }
}
