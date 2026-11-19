package de.seemoo.at_tracking_detection.residue

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import de.seemoo.at_tracking_detection.ATTrackingDetectionApplication
import de.seemoo.at_tracking_detection.database.models.Beacon
import de.seemoo.at_tracking_detection.database.models.device.BaseDevice
import de.seemoo.at_tracking_detection.database.models.device.DeviceType
import de.seemoo.at_tracking_detection.statistics.SendStatisticsWorker
import de.seemoo.at_tracking_detection.util.SharedPrefs
import kotlinx.coroutines.runBlocking
import java.time.LocalDateTime

/**
 * P04 B2 test hooks, identical in the stock and fenced test builds (never in a release): the emulator has no BLE, so the
 * harness inserts beacons with chosen collection times, drives consent through the app's own preference + scheduler path
 * (plus the consent log), and runs the donation worker now. am broadcast -n <pkg>/de.seemoo.at_tracking_detection.residue.TestHooks
 *   --es op insert --es addr AA:.. --ei n 5 --ei age_s 0 | --es op grant | --es op withdraw | --es op run
 */
class TestHooks : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val app = context.applicationContext as ATTrackingDetectionApplication
        val op = intent.getStringExtra("op") ?: return
        val pending = goAsync()
        Thread {
            try {
                when (op) {
                    "insert" -> runBlocking {
                        val addr = intent.getStringExtra("addr") ?: "AA:BB:CC:DD:EE:01"
                        val t = LocalDateTime.now().minusSeconds(intent.getIntExtra("age_s", 0).toLong())
                        if (app.deviceRepository.getDevice(addr) == null) app.deviceRepository.insert(BaseDevice(
                            deviceId = 0, uniqueId = "p04-$addr", address = addr, name = null, ignore = false, connectable = false,
                            payloadData = null, firstDiscovery = t, lastSeen = t, notificationSent = false, lastNotificationSent = null,
                            deviceType = DeviceType.AIRTAG, riskLevel = 0, lastCalculatedRiskDate = null, nextObservationNotification = null,
                            currentObservationDuration = null, additionalData = null))
                        repeat(intent.getIntExtra("n", 1)) {
                            app.beaconRepository.insert(Beacon(0, t, -60, addr, null, null, null, "UNKNOWN"))
                        }
                        ResidueEvents.log(context, "INSERT", "addr=$addr;n=${intent.getIntExtra("n", 1)};t=$t")
                    }
                    "grant" -> { ConsentLog.grant(context); SharedPrefs.shareData = true; app.backgroundWorkScheduler.scheduleShareData() }
                    "withdraw" -> { ConsentLog.withdraw(context); SharedPrefs.shareData = false; app.backgroundWorkScheduler.removeShareData() }
                    "run" -> { WorkManager.getInstance(context).enqueue(OneTimeWorkRequestBuilder<SendStatisticsWorker>().build()); ResidueEvents.log(context, "RUN_ENQUEUED", "") }
                }
                pending.resultData = "ok"
            } catch (e: Exception) {
                ResidueEvents.log(context, "HOOK_ERROR", "op=$op;error=$e"); pending.resultData = "error:$e"
            } finally { pending.finish() }
        }.start()
    }
}
