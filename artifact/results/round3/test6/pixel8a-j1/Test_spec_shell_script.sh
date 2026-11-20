#!/bin/bash
export PATH=/tmp/devicefarm-workspace/execution-32n478lo/shared-3vjk5anb/android-home-whtvzfa1/platform-tools:/tmp/devicefarm-workspace/execution-32n478lo/shared-3vjk5anb/android-home-whtvzfa1/build-tools/34.0.0:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/tmp/devicefarm-workspace/execution-32n478lo/shared-3vjk5anb/android-home-whtvzfa1/bundletool:$PATH
_df_install_phase()
{
echo ' '
echo '[DEVICEFARM] ########### Entering phase install ###########'
echo ' '
echo '[DeviceFarm] devicefarm-cli use python 3.12' 
devicefarm-cli use python 3.12 
echo '[DeviceFarm] python3 --version' 
python3 --version 
echo '[DeviceFarm] adb version' 
adb version 
}
_df_pre_test_phase()
{
echo ' '
echo '[DEVICEFARM] ########### Entering phase pre_test ###########'
echo ' '
echo '[DeviceFarm] adb -s $DEVICEFARM_DEVICE_UDID reverse tcp:8798 tcp:8798' 
adb -s $DEVICEFARM_DEVICE_UDID reverse tcp:8798 tcp:8798 
echo '[DeviceFarm] adb -s $DEVICEFARM_DEVICE_UDID reverse tcp:8799 tcp:8799' 
adb -s $DEVICEFARM_DEVICE_UDID reverse tcp:8799 tcp:8799 
echo '[DeviceFarm] adb -s $DEVICEFARM_DEVICE_UDID reverse tcp:8787 tcp:8787' 
adb -s $DEVICEFARM_DEVICE_UDID reverse tcp:8787 tcp:8787 
echo '[DeviceFarm] adb -s $DEVICEFARM_DEVICE_UDID reverse --list' 
adb -s $DEVICEFARM_DEVICE_UDID reverse --list 
echo '[DeviceFarm] adb -s $DEVICEFARM_DEVICE_UDID shell getprop ro.build.fingerprint' 
adb -s $DEVICEFARM_DEVICE_UDID shell getprop ro.build.fingerprint 
echo '[DeviceFarm] adb -s $DEVICEFARM_DEVICE_UDID shell pm list packages -i org.residuelab.tls' 
adb -s $DEVICEFARM_DEVICE_UDID shell pm list packages -i org.residuelab.tls 
echo '[DeviceFarm] adb -s $DEVICEFARM_DEVICE_UDID shell dumpsys package org.residuelab.tls | grep -i -E '"'"'installer|updateOwner|versionCode'"'"' || true' 
adb -s $DEVICEFARM_DEVICE_UDID shell dumpsys package org.residuelab.tls | grep -i -E 'installer|updateOwner|versionCode' || true 
echo '[DeviceFarm] adb -s $DEVICEFARM_DEVICE_UDID uninstall org.residuelab.tls; echo "UNINSTALL_TLS_EXIT=$?"' 
adb -s $DEVICEFARM_DEVICE_UDID uninstall org.residuelab.tls; echo "UNINSTALL_TLS_EXIT=$?" 
}
_df_test_phase()
{
echo ' '
echo '[DEVICEFARM] ########### Entering phase test ###########'
echo ' '
echo '[DeviceFarm] cd $DEVICEFARM_TEST_PACKAGE_PATH' 
cd $DEVICEFARM_TEST_PACKAGE_PATH 
COMMAND_EXIT_CODE=$?
if [ "$COMMAND_EXIT_CODE" != "0" ]; then
return $COMMAND_EXIT_CODE
fi
echo '[DeviceFarm] ADB=adb python3 artifact/followup/tls_suite.py --serial $DEVICEFARM_DEVICE_UDID --no-root --host 127.0.0.1 --start 0 --n 20 --cases control,early,buffered-fence,buffered-early,stall-small,stall-large,concurrent --out $DEVICEFARM_LOG_DIR/tls; echo "TLS_EXIT=$?"' 
ADB=adb python3 artifact/followup/tls_suite.py --serial $DEVICEFARM_DEVICE_UDID --no-root --host 127.0.0.1 --start 0 --n 20 --cases control,early,buffered-fence,buffered-early,stall-small,stall-large,concurrent --out $DEVICEFARM_LOG_DIR/tls; echo "TLS_EXIT=$?" 
COMMAND_EXIT_CODE=$?
if [ "$COMMAND_EXIT_CODE" != "0" ]; then
return $COMMAND_EXIT_CODE
fi
echo '[DeviceFarm] ADB=adb python3 artifact/followup/campaign.py --serial $DEVICEFARM_DEVICE_UDID --no-root --sink-host 127.0.0.1 --port 8787 --variants menqueue,mstart,mlayer,mfence,mboth --apkdir fixture/build/revision-apk --timeout 90 --schedules pending,kill,revoke --start 0 --trials 10 --seed test6-20261119 --out $DEVICEFARM_LOG_DIR/life; echo "LIFE_EXIT=$?"' 
ADB=adb python3 artifact/followup/campaign.py --serial $DEVICEFARM_DEVICE_UDID --no-root --sink-host 127.0.0.1 --port 8787 --variants menqueue,mstart,mlayer,mfence,mboth --apkdir fixture/build/revision-apk --timeout 90 --schedules pending,kill,revoke --start 0 --trials 10 --seed test6-20261119 --out $DEVICEFARM_LOG_DIR/life; echo "LIFE_EXIT=$?" 
COMMAND_EXIT_CODE=$?
if [ "$COMMAND_EXIT_CODE" != "0" ]; then
return $COMMAND_EXIT_CODE
fi
}
_df_post_test_phase()
{
echo ' '
echo '[DEVICEFARM] ########### Entering phase post_test ###########'
echo ' '
echo '[DeviceFarm] adb -s $DEVICEFARM_DEVICE_UDID reverse --remove-all' 
adb -s $DEVICEFARM_DEVICE_UDID reverse --remove-all 
}
handle_TERM()
{
echo '[DEVICEFARM] ########### Stop received, exit testspec execution ###########'
pkill -P $$
exit 130
}
handle_EXIT()
{
DEVICEFARM_EXIT_CODE=$?
echo '[DEVICEFARM] ########### Finish executing testspec ###########'
echo ' '
pkill -P $$
echo '[DEVICEFARM] ########### Setting upload permissions ###########'
echo ' '
chmod -R 777 $DEVICEFARM_SCREENSHOT_PATH 2>/dev/null 
echo DEVICEFARM_LOG_DIR: $DEVICEFARM_LOG_DIR >> /tmp/artifacts_description.txt 
chmod -R 777 $DEVICEFARM_LOG_DIR 2>/dev/null
echo ' '
exit $DEVICEFARM_EXIT_CODE
}
trap 'handle_TERM' 2 15
trap 'handle_EXIT' 0
cd /tmp/devicefarm-workspace/execution-32n478lo/test-package-qsyd2bfc
export CHROMEDRIVER_CDNURL=$DEVICEFARM_CHROMEDRIVER_CDNURL
export CHROMELABS_URL=$DEVICEFARM_CHROMEDRIVER_CDNURL
(
echo '[DEVICEFARM] ########### Start executing testspec ###########'
echo ' '
_df_shell_pid=$(exec sh -c 'echo $PPID')
handle_SUBSHELL_EXIT(){
pkill -P $_df_shell_pid
return 0
}
trap 'handle_SUBSHELL_EXIT' 0
_df_install_phase
_df_pre_test_phase
_df_test_phase
TEST_EXIT_CODE=$?
_df_post_test_phase
exit $TEST_EXIT_CODE
) &
SUB_SHELL_PID=$!
wait $SUB_SHELL_PID
SUB_SHELL_EXIT_CODE=$?
echo ' '
exit $SUB_SHELL_EXIT_CODE
