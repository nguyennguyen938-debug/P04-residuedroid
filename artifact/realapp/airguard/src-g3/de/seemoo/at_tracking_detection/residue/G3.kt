package de.seemoo.at_tracking_detection.residue

import android.content.Context
import android.content.Intent
import de.seemoo.at_tracking_detection.BuildConfig
import okhttp3.Call
import okhttp3.Interceptor
import okhttp3.Response
import java.net.InetAddress
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
 *  - G3c v5 (g3app5-card.md): SockLog, an OkHttp network interceptor in every OkHttp build, logs SOCKET_CONFIG with
 *    getSendBufferSize() of the connected socket per request; SndBuf16, a SocketFactory that sets SO_SNDBUF 16384 before
 *    connect, installed only in the stockcancel16 build (BuildConfig.RESIDUE_SNDBUF16).
 */
object G3 {
    @Volatile var ctx: Context? = null

    suspend fun <T> stock(c: Context, call: suspend () -> retrofit2.Response<T>): retrofit2.Response<T> {
        ctx = c.applicationContext
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

    object SockLog : Interceptor {
        override fun intercept(chain: Interceptor.Chain): Response {
            val s = chain.connection()?.socket()
            ctx?.let { ResidueEvents.log(it, "SOCKET_CONFIG", "path=${chain.request().url.encodedPath};requested_sndbuf=${if (BuildConfig.RESIDUE_SNDBUF16) 16384 else 0};actual_sndbuf=${s?.sendBufferSize ?: -1};kernel_sndbuf=${kern(s)};local_port=${s?.localPort ?: -1}") }
            return chain.proceed(chain.request())
        }
    }

    /** v5b: SO_SNDBUF as the kernel reports it (getsockopt on a dup of the socket's fd), the same call for every build;
     *  getSendBufferSize() differs by API (java.net.Socket: raw kernel value; NIO SocketChannel: halved). "-1;kernel_err=.." on failure. */
    @JvmStatic fun kern(s: Socket?): String = try {
        android.os.ParcelFileDescriptor.fromSocket(s).use { pfd ->
            // getsockoptInt is not in the public SDK: reflection on android.system.Os (hidden), else libcore.io.Libcore.os
            val args = arrayOf<Any>(pfd.fileDescriptor, android.system.OsConstants.SOL_SOCKET, android.system.OsConstants.SO_SNDBUF)
            val sig = arrayOf<Class<*>>(java.io.FileDescriptor::class.java, Int::class.javaPrimitiveType!!, Int::class.javaPrimitiveType!!)
            val v = try { android.system.Os::class.java.getMethod("getsockoptInt", *sig).invoke(null, *args) }
                    catch (e: Exception) { val os = Class.forName("libcore.io.Libcore").getField("os").get(null); os.javaClass.getMethod("getsockoptInt", *sig).invoke(os, *args) }
            "$v"
        }
    } catch (e: Throwable) { "-1;kernel_err=${(e.cause ?: e).javaClass.simpleName}" }

    object SndBuf16 : javax.net.SocketFactory() {
        private fun s(): Socket = Socket().apply { sendBufferSize = 16384 }
        override fun createSocket(): Socket = s()
        override fun createSocket(host: String, port: Int): Socket = s().apply { connect(InetSocketAddress(host, port)) }
        override fun createSocket(host: String, port: Int, la: InetAddress, lp: Int): Socket = s().apply { bind(InetSocketAddress(la, lp)); connect(InetSocketAddress(host, port)) }
        override fun createSocket(host: InetAddress, port: Int): Socket = s().apply { connect(InetSocketAddress(host, port)) }
        override fun createSocket(host: InetAddress, port: Int, la: InetAddress, lp: Int): Socket = s().apply { bind(InetSocketAddress(la, lp)); connect(InetSocketAddress(host, port)) }
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
