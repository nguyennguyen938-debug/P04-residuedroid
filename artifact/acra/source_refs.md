# Library sources inspected (fetched 2026-11-08; SHA-256 of fetched files)

## ACRA 5.14.2 (tag acra-5.14.2, https://github.com/ACRA/acra)
    56638adf66d2f4b5d159ea8aac510e76a1b3c4794c0a1f1fdb4981843f571a64  ACRA.kt
    da189e99eeefb02747c4f8f5b9ef2073599249f569dd4cac35e5fba08c410248  Adv.kt
    6658e3dfc9b2d09304f75e978c1143c9019b55b3ba2a1f124670f735709d6e3e  DefaultSenderScheduler.kt
    1ee9b9b1e91136346ac38a96c09d7a4f5ef3b6f6713e7806450b884ca15d4dc7  ErrorReporterImpl.kt
    0ed43803c527a8d663ac9ddd65b7a1a35d8b60a3712630050e9e3a038ac54cc6  JobSenderService.kt
    b5decc2cfb60c09e97f476a102c99a1666493ff2e18377de488e3f5c64d4585e  ReportDistributor.kt
    45df3025f10598948c4bcb8e57a5c2c900b1ab1e30c0fb5e4440058aa5ee4de2  SchedCfg.kt
    45538262fa6079178e2b01f5e6af62150d981647d583df78041d9883a90ef6ac  SchedulerStarter.kt
    a93dc7d3b0bb7ed21c79a9ec0e1542a858b5cf2392ecab702ac390b9612438a6  SendingConductor.kt
    f8943c45022efb2a6b3491144d6c85ea013779611a5b62c944a881e5312cfeca  StartupProcessorExecutor.kt

Findings: StartupProcessorExecutor.processReports schedules approved reports only if isAcraEnabled; JobSenderService.onStartJob -> SendingConductor.sendReports sends every approved report and never reads the enable flag; DefaultSenderScheduler builds JobInfo id 0 without setPersisted; AdvancedSenderScheduler.configureJob adds setRequiredNetworkType(requiresNetworkType) and drops setOverrideDeadline(0) when constrained.

## Matomo Android SDK 4.4 (tag 4.4, https://github.com/matomo-org/matomo-sdk-android)
    4ebca04b7d4814d1b9b51e437de2617dd927dc98b8afc75050ae25a227c73434  DefaultDispatcher.kt
    f471cb3ca76c72a3341563b9c6c7ea7bdada08043af8ff342ecb69c93438bc46  EventCache.java
    a7ec30d9bbb96bff6201461b3abc5e7d44788598ec96bfa87657d6099e1dcd22  Tracker.java

Findings: Tracker.setOptOut (L164-167) sets mOptOut and persists tracker.optout; Tracker.track (L503) skips submit when opted out; dispatch()/dispatchBlocking() return early when opted out; DefaultDispatcher loop (L184-250) drains and sends the event cache without consulting the opt-out flag, and setOptOut does not clear the queue. Not run on the emulator (SDK not on Maven Central).
