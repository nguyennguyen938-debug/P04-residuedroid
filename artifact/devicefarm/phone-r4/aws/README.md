# Vòng 4 trên AWS Device Farm: bộ chạy cho B (C dựng sẵn 24/11)

Ba thí nghiệm ưu tiên của vòng 4 (G3a, lifecycle có reboot và mất mạng, AirGuard lifecycle), chạy trên **máy thuê của AWS
Device Farm** thay cho điện thoại cá nhân. Card, patch và cổng pilot dùng chung với bộ máy cá nhân ở thư mục cha
(`../README.md`). Hạ tầng dựa trên Test 6: gói Appium Python, testspec custom environment, `plans/test6/run_df.sh`.

**Chưa có gì chạy trên Device Farm.** C đã kiểm offline:
- testspec sinh ra từ template parse được YAML, và từ chối khi còn ô trống;
- `make_package.sh` tạo đủ ba gói (thử với APK giả); gói lifecycle và AirGuard có patch đã áp;
- các script qua kiểm cú pháp.

Mỗi lần chạy tốn phút thiết bị, nên **cần leader đồng ý** từng lượt, như Test 6.

## Khác bộ máy cá nhân ở đâu

| | Máy cá nhân | Device Farm |
|---|---|---|
| Máy | máy của nhóm, Android 15 | Pixel 8a, Android 17 (như Test 6), không khóa màn hình |
| Harness chạy ở | Mac | host của Device Farm (`amazon_linux_2`), qua testspec |
| Thời lượng | chạy liền | job tối đa khoảng 100 phút; chia block hoặc trial thành nhiều job, mỗi job một thư mục |
| Reboot | được | **chưa biết**: pilot reboot riêng trước, job reboot tách khỏi job khác |
| EC2 cho G3a | Mac gọi API điều khiển | host Device Farm gọi API điều khiển, nên cổng 8800 phải mở cho host đó (dưới đây) |
| Chi phí | 0 | 0,17 USD mỗi phút thiết bị khi hết phút dùng thử; `run_df.sh` từ chối chạy nếu phút dùng thử không đủ |

## Chuẩn bị chung

1. Tài khoản AWS của nhóm (profile `p04`, vùng `us-west-2`), project và device pool Pixel 8a như Test 6.
2. Áp hai patch của bộ máy cá nhân vào nhánh của B nếu muốn chạy test offline; gói vẫn tự áp vào bản sao nếu HEAD chưa có.
3. Build APK trên Mac, như Test 6 và như bộ máy cá nhân:
   - G3a: `fixture/build/g3-apk/rl-tls.apk` (`VARIANTS=tls`, như G3a);
   - lifecycle: `fixture/build/revision-apk/rl-{menqueue,mstart,mlayer,mfence,mboth}.apk` (như Test 6);
   - AirGuard: `../build_airguard_phone.sh` → `realapp/airguard/build/phone/`.
4. Ba bước cho mỗi job (mọi file sinh ra để ngoài repo):
   ```
   bash artifact/devicefarm/phone-r4/aws/make_package.sh <task> <pkg.zip> [...]
   bash artifact/devicefarm/phone-r4/aws/make_spec.sh <task> <spec.yml> KEY=VALUE ...
   bash artifact/devicefarm/phone-r4/aws/upload_df.sh <project-arn> <pool-arn> <app.apk> <pkg.zip> <spec.yml> > uploads-<job>.env
   bash artifact/plans/test6/run_df.sh uploads-<job>.env <run-name> artifact/results/round3/phone-r4/aws/<task>/<job> <timeout>
   ```
   `run_df.sh` tải artifact về và giải nén; thư mục kết quả nằm dưới `unzipped/Customer_Artifacts/Host_Machine_Files/`.
5. Sau mỗi pilot: `python3 artifact/devicefarm/phone-r4/gates.py <g3a|life|airguard> <thư mục chứa schedule.jsonl hoặc calibration.json>`.

## G3a (ưu tiên 1)

1. USER đồng ý tạo EC2: `plans/test6/ec2/setup.sh --create`, `PROFILE_SET=b10v3 plans/test6/ec2/start.sh <ip>`.
2. **Mở cổng 8800 cho host Device Farm** (cần leader đồng ý; API có token, EC2 xóa ngay sau lượt):
   `aws ec2 authorize-security-group-ingress --group-id <sg p04-receiver> --protocol tcp --port 8800 --cidr 0.0.0.0/0`.
   Đóng lại sau lượt bằng `revoke-security-group-ingress` cùng tham số, hoặc `teardown.sh`.
3. Pilot (hiệu chỉnh):
   ```
   make_package.sh g3a pkg-g3a-pilot.zip --cert ~/.p04/ec2/cert-<ip> --token-file ~/.p04/ec2/token
   make_spec.sh g3a g3a-pilot.yml IP=<ip> RUNARGS="--calibrate 3"
   ```
   App tải lên: `rl-tls.apk`. Timeout 40 phút. Cổng: `gates.py g3a <dir>/g3a` (profile tách nhau, N theo thời gian block).
4. Final: gói mới có `--calib <pilot>/g3a/calibration.json`. Mỗi job 3 block, ví dụ
   `RUNARGS="--modes early,close,close2,fence,fence-abort --start 0 --trials 3 --durations calib/calibration.json"`, rồi
   `--start 3`, `--start 6`, `--start 9 --trials 1` (với N = 10). Timeout 100 phút mỗi job.
5. Phân tích: `followup/analyze_g3race.py <thư mục g3a của từng job> --out results/round3/phone-r4/aws/g3a/analysis --n <3N>`.
6. Gói G3a chứa token của EC2: xóa zip sau lượt, chạy `teardown.sh`.

## Lifecycle có reboot và mất mạng (ưu tiên 2)

1. Gói: `make_package.sh life pkg-life.zip`. App tải lên: `rl-mfence.apk` (testspec gỡ nó trước khi harness cài cả 5).
2. Pilot, **hai job riêng**:
   - `make_spec.sh life life-pnet.yml SCHED=netloss START=0 N=1`, timeout 20;
   - `make_spec.sh life life-preb.yml SCHED=reboot START=0 N=1`, timeout 20. Job này cho biết Device Farm có cho reboot không.
     Nếu job mất máy hoặc không có `boot_completed`, bỏ lịch reboot trên Device Farm và báo lại ở PR/issue.
   - Cổng: `gates.py life <dir>/life --schedules netloss` và `--schedules reboot`.
3. Final: `SCHED=netloss START=0 N=20` (timeout 80); reboot chia hai job `START=0 N=10` và `START=10 N=10` (timeout 100 mỗi job).
4. Phân tích: điền `manifest-life-df.json`, rồi `followup/analyze_test6.py --manifest devicefarm/phone-r4/aws/manifest-life-df.json --out results/round3/phone-r4/aws/life/analysis --n 20`.

## AirGuard lifecycle (ưu tiên 3)

1. Gói: `make_package.sh airguard pkg-ag.zip`. App tải lên: `airguard-fenced.apk`.
2. Pilot hai job: `SCHED=pending,kill,netloss START=0 N=1` và `SCHED=reboot START=0 N=1` (timeout 20 mỗi job).
   Cổng: `gates.py airguard <dir>/airguard --schedules pending,kill,netloss` và `--schedules reboot`.
3. Final: `SCHED=pending,kill,netloss` chia `START=0 N=10`, `START=10 N=10` (timeout 70 mỗi job); reboot (nếu pilot qua)
   `START=0 N=10`, `START=10 N=10` (timeout 80 mỗi job).
4. Phân tích: `followup/analyze_airguard.py <các thư mục airguard> --out results/round3/phone-r4/aws/airguard/analysis --n 20`.

## Phút thiết bị (ước lượng thô, cần pilot để chỉnh)

| Task | Pilot | Final | Tổng |
|---|---|---|---|
| G3a | khoảng 30 phút | 4 job, khoảng 250 phút | khoảng 280 phút |
| Lifecycle | 2 × khoảng 10 phút | netloss khoảng 50 phút, reboot khoảng 70 phút | khoảng 140 phút |
| AirGuard | 2 × khoảng 10 phút | khoảng 90 phút + reboot khoảng 60 phút | khoảng 170 phút |
| **Tổng** | | | **khoảng 590 phút** (gần 100 USD nếu tính tiền, chưa kể EC2) |

Thứ tự đề xuất: pilot reboot của lifecycle trước (rẻ, quyết định phần reboot của cả hai task), rồi G3a, rồi phần còn lại.

## Card

Dùng card nháp ở thư mục cha, sửa phần thiết bị (Pixel 8a trên Device Farm, Android 17), receiver và cách chia job, rồi
commit vào `plans/` trước lượt final. Kết quả báo cạnh số emulator và máy cá nhân (nếu có), không thay thế.
