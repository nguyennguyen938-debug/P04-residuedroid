# Experiment card (NHÁP của C): AirGuard trên điện thoại cá nhân (protocol v1)

Status: draft (C soạn 24/11; B sửa, chép sang `plans/airguard-phone-card.md` và commit trước lượt final)
Owner (experimenter): B (Duy)   Approved by (author): chờ leader

## 1. Question and claim
- Câu hỏi: trên điện thoại thật, AirGuard bản stock có chia sẻ beacon thu lúc opt-out sau khi người dùng đồng ý lại không, và
  bản fenced, layered thì sao? Đây là B2/G2b chạy trên máy thật.
- Claim đỡ được: hành vi của app thật trên một máy thật, theo cách đọc nút gạt của nhóm (paper đã ghi caveat này).
- Claim không đỡ được: Bluetooth thật (beacon vẫn là beacon giả qua test hook); server thật; các hãng khác.
- Chỗ trong paper: §7.4 (câu về AirGuard), abstract nếu có số máy thật.

## 2. Design
- Build: `stock, fenced, layered` trong cùng trial (như G2b), build cho máy bằng `build_airguard_phone.sh` (sink
  `http://127.0.0.1:<port>/`, cleartext thêm 127.0.0.1); mã nguồn và hook giữ nguyên.
- Lịch: `pending, kill, reboot, netloss` (như B2). kill qua `run-as`; reboot và netloss như card lifecycle (adb reverse).
- Đơn vị: trial; oracle v2 của B2 (`analyze_airguard.py`, thứ tự host).
- N: 20 trial mỗi lịch (như B2/G2b). Ước lượng 3 đến 4 giờ.
- Seed: `airguard-phone-20261125`. nbeacons 4, wait 90 s (mặc định B2).
- Thiết bị: như card lifecycle (không khóa màn hình có mật khẩu, sạc, Stay awake, Doze tắt khi chạy).
- Freeze: `results/round3/phone-r4/airguard/frozen-airguard-phone` (gồm SHA-256 của 3 APK).

## 3. Validity, exclusion, stopping, replacement
- Luật của `analyze_airguard.py` (như B2), cộng: trial reboot không có `boot_completed` thì không hợp lệ (B thêm vào
  analyze_airguard nếu chưa có).
- Dừng: sau N. Thay thế: lỗi môi trường, cả trial.
- Pilot: `pilot-*`, 1 trial mỗi lịch; cổng: không trial_error, hook ok, máy còn sống, đọc được log app, reboot xong.
- Rủi ro cần xem ở pilot: trên Android 15, broadcast tới app đã bị `pm clear` có thể không tới; worker có thể bị đóng
  băng khi app ở nền.

## 4. Analysis
- `followup/analyze_airguard.py results/round3/phone-r4/airguard/final --n 20`.
- Estimand: trial vi phạm theo build, unknown báo riêng, deficit hợp lệ (như B2).

## 5. Threats
- Construct: beacon giả qua hook; sink qua adb reverse (USB).
- External: một máy; cách đọc nút gạt (Appendix round3impl).

## 6. Outcome (điền sau khi chạy)
