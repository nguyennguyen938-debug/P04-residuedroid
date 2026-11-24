# Experiment card (NHÁP của C): Lifecycle có reboot và mất mạng trên điện thoại cá nhân (protocol v1)

Status: draft (C soạn 24/11; B sửa, chép sang `plans/lifecycle-phone-card.md` và commit trước lượt final)
Owner (experimenter): B (Duy)   Approved by (author): chờ leader

## 1. Question and claim
- Câu hỏi: trên điện thoại thật, sau reboot và khi mất kết nối tới server, các biến thể matched (cùng metadata) có vi phạm
  không? Test 6 chỉ có pending, kill, revoke vì máy thuê không reboot và không cắt mạng được.
- Claim đỡ được: "layered early và fence không vi phạm" mở rộng sang reboot và mất mạng trên một máy thật.
- Claim không đỡ được: Doze và standby bucket thật (harness ép bucket active, Doze tắt khi chạy); các hãng khác.
- Chỗ trong paper: §7.5 (câu về máy thật), §8 threats (bỏ câu "reboot và mất mạng chỉ có trên emulator" nếu chạy xong).

## 2. Design
- Biến thể: `menqueue, mstart, mlayer, mfence, mboth` trong cùng paired trial (như Test 6 và chiến dịch matched).
- Lịch: `reboot, netloss`, thứ tự cố định trong mỗi k (harness lặp k ngoài, lịch trong).
  - reboot: `adb reboot` (không root); cổng `adb reverse` được thêm lại ngay khi adbd lên.
  - netloss: gỡ cổng `adb reverse` 6 giây cho từng app (điện thoại nhận connection refused), tương ứng luật REJECT
    tới 10.0.2.2 trên emulator. Đây là cơ chế lỗi khác emulator; ghi rõ trong paper.
- Đơn vị: paired trial; tenant bị ảnh hưởng T1, T2, T4, T5, T8 như Test 6.
- N: 20 paired trial mỗi lịch (như Test 6). Ước lượng 2 đến 3 giờ.
- Seed: `lifecycle-phone-20261125`.
- Thiết bị: điện thoại cá nhân; **không có khóa màn hình có mật khẩu** trong lúc chạy (nếu không, bộ nhớ của app bị khóa sau
  reboot); sạc; Stay awake; Doze tắt trong lúc chạy và bật lại sau (script làm).
- Build: `fixture/build/revision-apk` (như Test 6); freeze `results/round3/phone-r4/lifecycle/frozen-lifecycle-phone`.
- Cửa sổ: `--timeout 90` như Test 6.

## 3. Validity, exclusion, stopping, replacement
- Luật của `analyze_test6.py` (gồm luật matched_oracle) cộng hai luật mới trong `phone-faults.patch`:
  netloss không có `net_verified_down == true` → "net cut not verified"; reboot không có `boot_completed` → "reboot not completed".
- Cảnh báo: luật "khoảng cách giữa hai action > 200 s" có thể loại trial reboot nếu máy khởi động chậm; pilot ghi
  `max_action_gap_s` để kiểm.
- Dừng: sau N. Thay thế: lỗi môi trường, cả paired trial, ID mới (resume của campaign.py).
- Pilot: `pilot-*`, 1 paired trial mỗi lịch; cổng cơ chế trong `run_lifecycle_phone.sh`.

## 4. Analysis
- `followup/analyze_test6.py --manifest devicefarm/phone-r4/manifest-lifecycle-phone.json` (điền model/Android vào manifest).
- Estimand như Test 6: trial có tenant bị ảnh hưởng vi phạm, theo biến thể; unknown báo riêng; deficit hợp lệ.
- Key: C thêm (`devLife*` theo lịch hoặc key mới), báo cạnh Test 6.

## 5. Threats
- Internal: netloss bằng adb reverse khác iptables của emulator; tốc độ khởi động máy thật.
- Construct: socket kết thúc ở adbd (qua USB), như Test 6, nên không đo đường mạng.
- External: một máy, Android 15.

## 6. Outcome (điền sau khi chạy)
