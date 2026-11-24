#!/bin/bash
export PATH=/tmp/devicefarm-workspace/execution-5r2s3ffh/shared-u48pic60/android-home-e6rd5w6l/platform-tools:/tmp/devicefarm-workspace/execution-5r2s3ffh/shared-u48pic60/android-home-e6rd5w6l/build-tools/34.0.0:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/tmp/devicefarm-workspace/execution-5r2s3ffh/shared-u48pic60/android-home-e6rd5w6l/bundletool:$PATH
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
echo '[DeviceFarm] adb -s $DEVICEFARM_DEVICE_UDID shell getprop ro.build.fingerprint' 
adb -s $DEVICEFARM_DEVICE_UDID shell getprop ro.build.fingerprint 
echo '[DeviceFarm] adb -s $DEVICEFARM_DEVICE_UDID shell '"'"'command -v nc || toybox nc --help >/dev/null 2>&1 && echo NC_OK || echo NC_MISSING'"'"'' 
adb -s $DEVICEFARM_DEVICE_UDID shell 'command -v nc || toybox nc --help >/dev/null 2>&1 && echo NC_OK || echo NC_MISSING' 
echo '[DeviceFarm] adb -s $DEVICEFARM_DEVICE_UDID uninstall org.residuelab.mfence; echo "UNINSTALL_EXIT=$?"' 
adb -s $DEVICEFARM_DEVICE_UDID uninstall org.residuelab.mfence; echo "UNINSTALL_EXIT=$?" 
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
echo '[DeviceFarm] ADB=adb python3 artifact/followup/campaign.py --serial $DEVICEFARM_DEVICE_UDID --no-root --sink-host 127.0.0.1 --phone-faults --port 8787 --variants menqueue,mstart,mlayer,mfence,mboth --apkdir fixture/build/revision-apk --timeout 90 --schedules netloss --start 0 --trials 1 --seed lifecycle-df-20261125 --out $DEVICEFARM_LOG_DIR/life; echo "LIFE_EXIT=$?"' 
ADB=adb python3 artifact/followup/campaign.py --serial $DEVICEFARM_DEVICE_UDID --no-root --sink-host 127.0.0.1 --phone-faults --port 8787 --variants menqueue,mstart,mlayer,mfence,mboth --apkdir fixture/build/revision-apk --timeout 90 --schedules netloss --start 0 --trials 1 --seed lifecycle-df-20261125 --out $DEVICEFARM_LOG_DIR/life; echo "LIFE_EXIT=$?" 
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
echo '[DeviceFarm] adb -s $DEVICEFARM_DEVICE_UDID reverse --remove-all || true' 
adb -s $DEVICEFARM_DEVICE_UDID reverse --remove-all || true 
echo '[DeviceFarm] for p in menqueue mstart mlayer mfence mboth; do adb -s $DEVICEFARM_DEVICE_UDID uninstall org.residuelab.$p || true; done' 
for p in menqueue mstart mlayer mfence mboth; do adb -s $DEVICEFARM_DEVICE_UDID uninstall org.residuelab.$p || true; done 
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
cd /tmp/devicefarm-workspace/execution-5r2s3ffh/test-package-7oayyz7l
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
