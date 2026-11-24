# Vòng 4 trên điện thoại cá nhân: bộ chạy cho B (C dựng sẵn 24/11)

Leader yêu cầu: chạy lại trên **điện thoại cá nhân** những thí nghiệm hiện chỉ có trên emulator, theo thứ tự ưu tiên.
C đã làm ưu tiên 0 và dựng sẵn ưu tiên 1 đến 3. Các mục còn lại chỉ được ghi lại, chưa dựng.

**Chưa có gì chạy trên máy thật.** Các patch đã được kiểm offline: áp sạch, biên dịch được, test qua. Script và cổng pilot đã
chạy thử trên log giả lập. Cổng pilot trên máy thật là lần kiểm đầu tiên.

Theo quy tắc nghiên cứu, mỗi thí nghiệm có card, pilot, cổng, freeze, RUNLOG, EXCLUSIONS và thư mục mới. Kết quả được báo
**cạnh** số emulator, không thay thế. Hạn đóng băng dữ liệu: 29/11.

## Ưu tiên

| # | Việc | Trạng thái | Giờ máy (ước lượng) |
|---|---|---|---|
| 0 | Đưa số layered early và job-start trên hai máy thuê (Test 6) vào paper | **Xong** (C, key `devLifeLayer*`, `devLifeStart*`) | 0 |
| 1 | G3a (race theo điểm commit W, 5 arm) trên máy cá nhân | **Dựng sẵn**: `run_g3a_phone.sh`, `card-g3a-phone.md`. Không cần sửa code | khoảng 4 giờ |
| 2 | Lifecycle matched có reboot và mất mạng | **Dựng sẵn**: `phone-faults.patch`, `run_lifecycle_phone.sh`, `card-lifecycle-phone.md` | 2 đến 3 giờ |
| 3 | AirGuard lifecycle (stock, fenced, layered) | **Dựng sẵn**: `airguard-phone.patch`, `build_airguard_phone.sh`, `run_airguard_phone.sh`, `card-airguard-phone.md` | 3 đến 4 giờ |
| 4 | AirGuard rút giữa lúc donation (G3c) | Chưa dựng: cần build có `apply_g3.sh` với sink 127.0.0.1, receiver có giới hạn tốc độ (EC2) cho sink AirGuard, bỏ capture | khoảng 1,5 giờ |
| 5 | Byte rời máy theo send buffer (P4) | Chưa dựng: capture ở laptop làm điểm phát Wi-Fi; đại lượng đo khác emulator, cần card mới | 6 đến 10 giờ |
| 6 | G2a, P3 | Gộp vào #1 (G3a có cả arm `close` và `--warm-revision` như P3) | 0 |
| 7 | ACRA, Matomo | Chưa dựng: kiểm địa chỉ sink của test app (emulator dùng 10.0.2.2) và thêm cờ host như `real-device.patch` | 2 đến 3 giờ |
| 8 | TLS suite, socket matrix, split policy | TLS suite chạy được ngay (`tls_suite.py --no-root --host 127.0.0.1` qua adb reverse, như Test 6) | 1 đến 3 giờ |
| 9 | Label mutants | Chưa dựng: harness mutation cần `--no-root` như `campaign.py` | khoảng 4 giờ |
| 10 | Cost sweep | Không cần: đã có G3d trên máy cá nhân | 0 |

Trước 29/11, leader đề xuất: #1, rồi #2 hoặc #3 nếu còn thời gian.

**Chạy trên máy thuê AWS Device Farm thay cho máy cá nhân:** xem `aws/README.md`. Card, patch và cổng pilot (`gates.py`)
dùng chung; chỉ khác cách đóng gói, testspec và chia job.

## 1. Chuẩn bị máy (USER làm, B kiểm bằng preflight)

1. USB debugging bật, chấp nhận khóa RSA của Mac. Cắm sạc. Developer options, bật Stay awake.
2. **Bỏ khóa màn hình có mật khẩu/PIN/hình vẽ trong lúc chạy #2 và #3** (để None hoặc Swipe). Nếu không, sau reboot bộ nhớ của
   app bị khóa cho tới khi mở khóa, job không chạy và harness không đọc được log. Đặt lại sau khi chạy xong.
3. `bash devicefarm/phone-r4/preflight_r4.sh <serial>` phải in `PREFLIGHT OK` (chỉ đọc, không đổi gì trên máy).
4. Script chạy tắt Doze trong lúc chạy (`dumpsys deviceidle disable`) và bật lại sau. Không đổi cài đặt nào khác của máy.
5. Không dùng máy vào việc khác trong lúc chạy. Gỡ các app test sau khi xong.

## 2. #1: G3a trên máy cá nhân

Dùng đúng hạ tầng của Test 1 trên máy này (`plans/test1-phone/README.md`): receiver `receiver_b.py` trên EC2, giới hạn
upload theo `PROFILE_SET=b10v3`. Không cần patch: `race_suite.py` đã có `--receiver --host --no-root --g3`.

1. Build G3 (`fixture/build/g3-apk/rl-tls.apk`, `VARIANTS=tls`) như G3a.
2. USER xác nhận tạo EC2, rồi `plans/test6/ec2/setup.sh --create` và `PROFILE_SET=b10v3 plans/test6/ec2/start.sh <ip>`.
3. Chép `card-g3a-phone.md` sang `plans/g3a-phone-card.md`, sửa nếu cần, commit.
4. `bash devicefarm/phone-r4/run_g3a_phone.sh pilot <ip> <serial>`: hiệu chỉnh 3 lần mỗi ô, cổng profile, quy tắc N.
5. Ghi N vào card, commit. `bash devicefarm/phone-r4/run_g3a_phone.sh final <ip> <serial> <N>`.
6. Dọn: `plans/test1-phone/cleanup_phone.sh <serial>`, `plans/test6/ec2/teardown.sh <instance-id>`, RUNLOG, card §6.

Không có capture và marker (máy thật không có `-tcpdump` của emulator). Primary là đếm từ log của app, như G3a.

## 3. #2: Lifecycle có reboot và mất mạng

1. Xem và áp `git apply artifact/devicefarm/phone-r4/phone-faults.patch` (sửa `followup/campaign.py`,
   `followup/analyze_test6.py`, thêm `followup/test_campaign_phonefaults.py`). Chạy
   `python3 followup/test_campaign_phonefaults.py` và `python3 followup/test_analyze_test6.py`.
2. Patch thêm cờ `--phone-faults` (cần `--no-root --sink-host 127.0.0.1`):
   - reboot = `adb reboot`, harness thêm lại cổng `adb reverse` ngay khi adbd lên;
   - netloss = gỡ cổng `adb reverse` trong 6 giây cho từng app, điện thoại nhận connection refused (tương ứng luật REJECT
     tới 10.0.2.2 trên emulator; không đụng radio hay firewall);
   - `analyze_test6.py` thêm luật: netloss chưa xác nhận mạng đứt, hoặc reboot không có `boot_completed`, thì trial không hợp lệ.
   Emulator không bị ảnh hưởng: không có cờ thì hành vi y như cũ.
3. Chép `card-lifecycle-phone.md` sang `plans/lifecycle-phone-card.md`, commit.
4. `bash devicefarm/phone-r4/run_lifecycle_phone.sh pilot <serial>`, xem `gate.json` (gồm `max_action_gap_s` của reboot:
   luật cũ loại trial có khoảng nghỉ trên 200 giây).
5. `bash devicefarm/phone-r4/run_lifecycle_phone.sh final <serial> 20`. Điền model/Android vào
   `manifest-lifecycle-phone.json` trước khi phân tích.

## 4. #3: AirGuard lifecycle

1. Xem và áp `git apply artifact/devicefarm/phone-r4/airguard-phone.patch` (sửa `followup/campaign_airguard.py`,
   `realapp/airguard/apply.sh`). Mặc định của emulator không đổi.
2. Patch thêm `--phone`: không `adb root`, đọc log bằng `run-as`, kill qua `run-as`, sink qua `adb reverse` (8795, 8796,
   8797), netloss và reboot như #2. `apply.sh` đọc `CLEARTEXT_HOSTS` để cho phép cả 127.0.0.1.
3. `bash devicefarm/phone-r4/build_airguard_phone.sh <AirGuard checkout d515c534> <work dir>` →
   `realapp/airguard/build/phone/`.
4. Chép card, commit; `run_airguard_phone.sh pilot <serial>`; rồi `final <serial> 20`.
5. Xem ở pilot: broadcast tới app sau `pm clear` có tới không, và worker có bị đóng băng ở nền trên Android 15 không.

## 5. Sau khi chạy

- C thêm key (ví dụ `gtrPhone*`, key lifecycle theo lịch, key AirGuard máy thật) và viết vào paper, cạnh số emulator.
- Bỏ câu "reboot và mất mạng chỉ có trên emulator" ở §8 nếu #2 xong.
- Kết quả nào cũng báo, kể cả khi khác emulator.
