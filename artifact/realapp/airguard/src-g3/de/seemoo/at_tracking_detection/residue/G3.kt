package de.seemoo.at_tracking_detection.residue

import android.content.Context
import android.content.Intent
import de.seemoo.at_tracking_detection.BuildConfig
import okhttp3.Call
import okhttp3.Interceptor
import okhttp3.Response
import java.net.InetSocketAddress
import java.net.Socket
import java.util.concurrent.ConcurrentHashMap

/**
 * P04 group 3 (g3app-card.md), test builds only, applied by apply_g3.sh on top of apply.sh:
 *  - stock(): logs the end of the stock Retrofit donation (DONATION_OK / DONATION_ERROR), so the harness knows when the
 *    upload ended; the call itself is unchanged.
 *  - InFlight: OkHttp interceptor registry of in-flight calls, installed only in the stock-cancel build
 *    (BuildConfig.RESIDUE_CANCEL); on withdrawal every registered call gets Call.cancel().
 *  - afterWithdraw(): after the app's own withdrawal path (consent log, preference, scheduler), [cancel], then
 *    WITHDRAW_DONE and one TCP connection to the host marker port carrying the trial id (ack position in the capture).
 *  - mark(): the same connection on demand (hook op mark), used by the harness as the start marker of each build-trial.
 */
object G3 {
    suspend fun <T> stock(c: Context, call: suspend () -> retrofit2.Response<T>): retrofit2.Response<T> {
        ResidueEvents.log(c, "DONATION_START", "stock=1")
        try {
            val r = call(); ResidueEvents.log(c, "DONATION_OK", "stock=1;code=${r.code()}"); return r
        } catch (e: Throwable) { ResidueEvents.log(c, "DONATION_ERROR", "stock=1;error=$e"); throw e }
    }

    object InFlight : Interceptor {
        private val live = ConcurrentHashMap.newKeySet<Call>()
        override fun intercept(chain: Interceptor.Chain): Response {
            live.add(chain.call())
            try { return chain.proceed(chain.request()) } finally { live.remove(chain.call()) }
        }
        fun cancelAll(): Int { var n = 0; for (c in live) { c.cancel(); n++ }; return n }
    }

    fun afterWithdraw(c: Context, i: Intent) {
        if (BuildConfig.RESIDUE_CANCEL) ResidueEvents.log(c, "CANCEL_DONE", "calls=${InFlight.cancelAll()}")
        ResidueEvents.log(c, "WITHDRAW_DONE", "tid=${i.getStringExtra("tid") ?: ""}")
        mark(c, i)
    }

    /** One TCP connection to the host marker port carrying the id (op mark: the harness's start marker; after withdrawal: the ack). */
    fun mark(c: Context, i: Intent) {
        val tid = i.getStringExtra("tid") ?: ""
        val port = i.getIntExtra("marker", 0)
        if (port <= 0) return
        val res = try {
            Socket().use { s ->
                s.tcpNoDelay = true; s.connect(InetSocketAddress("10.0.2.2", port), 3000)
                s.getOutputStream().apply { write("$tid\n".toByteArray()); flush() }; "local_port=${s.localPort}"
            }
        } catch (e: Exception) { "error=$e" }
        ResidueEvents.log(c, "MARKER_SENT", "port=$port;tid=$tid;$res")
    }
}
