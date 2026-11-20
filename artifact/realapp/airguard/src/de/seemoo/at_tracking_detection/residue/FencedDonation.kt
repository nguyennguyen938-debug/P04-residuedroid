package de.seemoo.at_tracking_detection.residue

import android.content.Context
import com.google.gson.GsonBuilder
import de.seemoo.at_tracking_detection.BuildConfig
import de.seemoo.at_tracking_detection.database.relations.DeviceBeaconNotification
import de.seemoo.at_tracking_detection.util.converter.LocalDateTimeConverter
import org.residuelab.transport.HttpTransport
import java.net.URL
import java.time.LocalDateTime
import java.time.ZoneId
import java.util.UUID

/**
 * P04 B2 fenced variant: the worker's donation body (same Gson configuration as ApiModule.provideGson) is sent through
 * ResidueDroid's chunk-fenced HttpTransport; every chunk re-checks that consent is open and covers every item's collection time.
 * Returns true if the upload completed or was blocked by policy (blocked data must not be retried), false to retry.
 */
object FencedDonation {
    fun send(c: Context, devices: List<DeviceBeaconNotification>): Boolean {
        val gson = GsonBuilder().setDateFormat("yyyy-MM-dd'T'HH:mm:ssZ")
            .registerTypeAdapter(LocalDateTime::class.java, LocalDateTimeConverter()).create()
        val body = gson.toJson(devices).toByteArray()
        val zone = ZoneId.systemDefault()
        val ts = devices.flatMap { d -> d.beacons.map { it.receivedAt } + d.notifications.map { it.createdAt } }
            .map { it.atZone(zone).toInstant().toEpochMilli() }
        val url = URL(BuildConfig.API_BASE_ADDRESS)
        val id = UUID.randomUUID().toString()
        ResidueEvents.log(c, "DONATION_START", "request=$id;items=${ts.size};bytes=${body.size}")
        return try {
            HttpTransport.postMode(url.host, if (url.port > 0) url.port else 80, url.path.trimEnd('/') + "/donate_data", body,
                ConsentLog.lock(c), { ConsentLog.permitted(c, ts) }, true, false,
                { kind, detail -> ResidueEvents.log(c, kind, detail) }, id, 1, HttpTransport.CHUNK, 60000)
            ResidueEvents.log(c, "DONATION_OK", "request=$id"); true
        } catch (e: HttpTransport.Denied) {
            ResidueEvents.log(c, "DONATION_BLOCKED", "request=$id"); true
        } catch (e: Exception) {
            ResidueEvents.log(c, "DONATION_ERROR", "request=$id;error=$e"); false
        }
    }
}
