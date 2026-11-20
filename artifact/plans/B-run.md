# Experiment Plan — vai B (thí nghiệm), round 3

Trình bày lại phần vai B của `PLAN-ROUND3.md` theo khung skill `experiment-plan`. **Nội dung lấy nguyên từ plan của
nhóm, không thêm việc.** Nguồn: `[R3]` = `PLAN-ROUND3.md`, `[HB]` = `HUONG-DAN-B.md`, `[DF]` = `artifact/devicefarm/README.md`,
`[MUT]` = `artifact/mutation/README.md`, `[RT]` = `artifact/scripts/render_tests.py` (SCHEMA). Chỗ plan không nói thì ghi
*plan không nêu*.

**Vấn đề**: review mô phỏng cho weak reject; round 3 thêm 6 test để trả lời R1, R2, R3 [R3 §Sáu test].
**Vai B**: một người, một máy Mac chạy emulator, là chỗ nghẽn của nhóm [R3 "Khác bản 1"].
**Mốc cứng**: data freeze **29/11**, đăng ký abstract 27/11, nộp bài 4/12 AoE [R3, HB].
**Nhánh**: `b-exp` tạo từ `origin/main`, gộp qua PR [HB §Bắt đầu]. Bản trước round 3: tag `snapshot-20261117`.

## Phạm vi sở hữu [R3 §Sở hữu file, HB]
- B sở hữu `artifact/**`, cùng `06-implementation` và appendix "Artifact".
- Trừ: `scripts/render*.py`, `revision/render_revision.py`, `followup/render.py`, `artifact/mutation/**`, `artifact/triage/`,
  `artifact/survey/`, `artifact/devicefarm/**`. Đọc được; cần sửa thì báo C (mutation thuộc A).
- B giữ hàng đợi emulator: không ai khác chạy emulator trên máy của B [R3 nguyên tắc 5].
- Giao số cho C: đúng một file `artifact/results/round3/summary.json`, dạng `{tên: giá trị}` phẳng, tên theo `SCHEMA` trong
  `render_tests.py`; không gõ số tay vào `.tex` [HB §Cách giao số, R3 nguyên tắc 1].

## Claim Map (test → reviewer → khóa summary.json)
| Test | Trả lời | Việc B | Khóa trong `summary.json` [HB, RT] | Mức [R3] |
|---|---|---|---|---|
| 1 Race tự nhiên, payload lớn, mạng chậm | R1 | B10 | `raceTrials`, `raceEdgeLayer`, `raceEdgeFence`, `raceThreegLayer`, `raceThreegFence`, `raceLteLayer`, `raceLteFence`, `racePredPct`, `raceObsPct` | Bắt buộc |
| 2 Đột biến nhãn + bộ kiểm nhãn | R2 | B12 (A viết code) | `mutTrials`, `mutOneLeak`, `mutOneFlagged`, `mutOneWrong`, `mutTwoLeak`, `mutTwoFlagged`, `mutTwoWrong`, `mutThreeDeficit` | Bắt buộc |
| 3 Lời hứa thật trong app | R3 | — (C đã xong) | không cần khóa từ B | Bắt buộc |
| 4 Lifecycle Android 14 và 15 | R1, R3 | B11 | `lifeFourteenTrials`, `lifeFourteenLayer`, `lifeFourteenFence`, `lifeFifteenTrials`, `lifeFifteenLayer`, `lifeFifteenFence` | Cắt được |
| 5 Quét chunk và số sender | R1 | B4 | `sweepAckSmallMs`, `sweepAckLargeMs`, `sweepCpuSmall`, `sweepCpuLarge` | Cắt đầu tiên |
| 6 Điện thoại thật (AWS Device Farm) | R1, R3 | Test 6 | `devModel`, `devAndroid`, `devTrials`, `devEarlyComplete`, `devFenceAfterAck` | Cắt được phần lifecycle |
| (không phải test) App thật end-to-end | P1 | B1 → B2 | *plan không nêu khóa riêng*; raw và `summary.json` | theo S1 |
| (không phải test) Chính sách tách lô | R2 | B3 | *plan không nêu khóa riêng*; raw và `summary.json` | — |

## Các block

### B0 — Môi trường, `make apks`, 1 trial smoke · hạn 19/11 [R3, HB]
- Mac Apple Silicon, ảnh arm64 như paper; JDK 17, SDK, emulator; `make apks`; 1 trial smoke. Đầu ra: ghi chú môi trường.
- Trạng thái 18/11: JDK 17, SDK, emulator 37.2.13, image android-33 arm64 rev 17, AVD `P04AvdB`, `make apks` xong (RUNLOG
  2026-11-18). Còn: trial smoke.

### B1 — Sàng app thật · hạn **21/11 (S1)** [R3, HB]
- AirGuard (`de.seemoo.at_tracking_detection`), Fedilab (`fr.gouv.etalab.mastodon`), CastBay (`com.weenas.castbay`).
- Mỗi app kiểm 3 điều: build được từ source không; lời hứa nói gì về dữ liệu đang chờ; đường gửi có bọc được không.
- Đầu ra: quyết định đi tiếp/bỏ ở S1. Dự phòng: giữ ACRA và Matomo, nói rõ giới hạn [R3 §Rủi ro].

### B11 — Test 4: Android 14 và 15 · chạy đêm 20 và 21/11, hạn 22/11 [R3, HB]
- AVD Android 14 và 15 arm64; lịch pen, kill, reb, net; một baseline yếu, layered early, ResidueDroid. Không cần code mới.
- Số trial, AVD/port cụ thể: *plan không nêu*.

### A10 (phần còn lại) — chạy triage · hạn 22/11 [HB]
- `python artifact/triage/find_callers.py artifact/acra/build/apk/acrafence.apk artifact/matomo/build/matomo.apk`, gửi kết quả cho A.
- Cần `matomo/build/matomo.apk` (`bash matomo/build.sh`, theo artifact README).

### B3 — Tách lô · hạn 24/11 [R3, HB]
- Cài chính sách S0 vào `ChunkFence` và transport: fence chặn trước khi có byte nào ra socket thì chia item theo nhãn; item
  bị cấm loại hẳn, item hợp lệ thành request mới và qua fence lại; tối đa 1 lần tách mỗi attempt; đã có byte được nhận thì
  không tách. Lý thuyết ở §5 "Splitting blocked requests".
- 3 điều kiện × 20 trial; đo tỷ lệ giữ được thư hợp lệ và số lần gửi lại thành công. 3 điều kiện cụ thể: *plan không nêu*.

### B10 — Test 1: race tự nhiên · hạn 25/11 [R3, HB]
- Payload theo kích thước thật (báo cáo ACRA vài trăm KB, lô analytics, backup vài MB); mạng emulator EDGE, 3G, LTE; thời
  điểm rút ngẫu nhiên đều trong suốt upload, không dùng barrier; layered early so với fence.
- Đo: tỷ lệ trial có byte được nhận sau ack; đối chiếu Eq. 2. Số trial mỗi profile: *plan không nêu* (`raceTrials`).

### B4 (+ test 5) — Chi phí transport · hạn 26/11 [R3, HB]
- Thứ tự ngẫu nhiên, tải đồng thời; chunk 1, 4, 16, 64 KiB × 1, 2, 4, 8, 16 sender. Thiếu giờ máy thì thu lưới lại.

### B12 — Test 2: đột biến nhãn · hạn 28/11 [R3, HB, MUT]
- Build theo `[MUT] §Build`: I0 áp cho mọi bản; base, M1 union-latest, M2 stale-epoch, M3 extras-drop; mỗi bản `VARIANTS=mfence
  OUTDIR=build/apk_mut_$m`; `git checkout -- artifact/fixture/src` sau mỗi bản (không commit patch).
- Chạy: `followup/campaign.py --variants mfence --schedules pending,reboot --trials 20 --apkdir fixture/build/apk_mut_$m
  --out results/mutation/$m`, từng mutant một trên cùng AVD. README ghi `--serial emulator-5600 --avd P04AvdA --port 8795`.
- Phân tích: `mutation/label_check.py`; oracle `followup/matched_oracle.py` cần thêm tham số thư mục chạy (việc của B).
- Chạy thêm trên app thật nếu B2 xong trước 27/11.

### Test 6 — Điện thoại thật qua AWS Device Farm · hạn 28/11 [R3 §Quyết định, HB, DF]
- B (Duy) lo hết: tạo tài khoản AWS, bật thanh toán, kiểm 1.000 phút dùng thử; áp `real-device.patch` (xem, không commit
  thẳng); build `fixture/build/tls-apk/rl-tls.apk`; tạo cặp chứng chỉ test theo `followup/tls-cert/README.md`.
- Chạy được: các case TLS barrier, backpressure, `control`, `early`, `concurrent` của `followup/tls_suite.py`. Lifecycle fixture
  chưa chạy được (`10.0.2.2`, `sqlite3` root); reboot và cắt mạng chưa biết.
- Thứ tự: chạy thử 1 máy `--n 1` (kiểm `adb root` bị từ chối không làm hỏng lượt, `run-as` đọc `revision.jsonl`,
  `barrier_seen` true, receiver nhận đủ `control`), rồi 2 máy khác hãng (Pixel, Samsung) `--n 20`.
- Receiver: chế độ A (trên host Device Farm, qua `adb reverse`/USB) cho barrier và backpressure; chế độ B (EC2 `us-west-2`,
  mạng thật) cần cho test 1 trên máy thật, chưa làm. Mọi lượt phải ghi chế độ receiver [HB, DF].
- Chi phí: [DF] ~100 phút (2 máy + chạy thử, chỉ TLS/backpressure); [R3] ~1.100 phút nếu gồm test 1 và lifecycle.

### B2 — App thật end-to-end (nếu S1 đi tiếp) · hạn 28/11 [R3, HB]
- Tích hợp; lịch pen, kill, reb, net (thêm fstop nếu kịp), mỗi lịch 20 trial; bản gốc so với bản có fence, kèm luồng được
  phép làm đối chứng.

### B7 — Data freeze · **29/11** [R3, HB]
- Commit raw, `summary.json`, PROTOCOL, EXCLUSIONS. Sau mốc này không chạy thêm.

### B8 — Văn bản · hạn 2/12 [R3, HB]
- §6, appendix Artifact. Sửa tài liệu cũ: `INTEGRATION.md` và `artifact-revision-audit.md` còn ghi "không có HTTPS",
  `STATUS.md` ghi 17 trang, `PLAN.md` ghi "review anonymous"; cập nhật README, STATUS, PLAN.

### B9 — Rebuild độc lập · hạn 2/12 [R3, HB]
- Nhờ một người chưa đụng dự án clone repo và chạy `make all`; lưu log.

## Thứ tự chạy — hàng đợi emulator [R3 §Hàng đợi]
Mục tiêu, B được đổi thứ tự; việc dài chạy qua đêm.

| Ngày | B làm ban ngày | Emulator chạy |
|---|---|---|
| 19/11 | B0 | Smoke |
| 20/11 | B1 | B11 Android 14 |
| 21/11 | B1, báo S1 | B11 Android 15 |
| 22/11 | Code B10 | B4 cùng test 5 |
| 23/11 | Code B3, bắt đầu B2 | B10 |
| 24/11 | B2 | B3 |
| 25/11 | B2 | B12 trên fixture; chạy lại B10 nếu cần |
| 26–27/11 | B2 | B2 |
| 28/11 | Kiểm số | B12 trên app thật, chạy bù |
| 29/11 | B7 data freeze | — |
Test 6 chạy trên Device Farm, không chiếm emulator; hạn 28/11.

## Phụ thuộc và điểm đồng bộ [R3]
- S1 (21/11): B báo đi tiếp/bỏ app thật. S3 (29/11): data freeze, B → C.
- A9 → B12 (trong lúc chờ: chạy B10, B3 trước). B7 → C7.

## Ngân sách
- Emulator: một Mac, theo hàng đợi trên; số giờ cụ thể *plan không nêu*.
- Device Farm: 0,17 USD/phút; có thể có 1.000 phút dùng thử một lần, phải kiểm; ước [DF] ~100 phút, [R3] ~1.100 phút
  (~190 USD); EC2 receiver < 10 USD.

## Rủi ro và dự phòng [R3 §Rủi ro, HB]
- App thật không build/tích hợp kịp → dự phòng ACRA + Matomo, nói rõ giới hạn; test 2 vẫn chạy trên fixture.
- Device Farm không cho reboot/cắt mạng → giữ reb và net ở emulator, ghi trong §7a.
- Lượt Device Farm giới hạn thời gian (nguồn ngoài: 150 phút) → chia lô nhỏ.
- Máy thật cắm sạc không vào Doze → `dumpsys battery unplug`, `dumpsys deviceidle force-idle`, ghi trong §7a.
- Chạy trên x86_64 thay vì arm64 → không gộp số thời gian với campaign cũ.
- `UpJob.onStopJob` trả `false` nên job dừng lúc tắt máy không được xếp lại (nguồn của 448 thư thiếu ở reboot); nếu đổi hành vi
  này cho lượt mới thì ghi PROTOCOL.

## Thứ tự cắt khi trễ [R3, HB]
1. Bỏ test 5. 2. Bỏ phần lifecycle của test 6. 3. Thu test 4 còn một bản Android.
Test 1–3 phải giữ. Không kịp 29/11 thì bỏ khỏi thân bài, không chạy đuổi.

## Checklist cuối
- [ ] Mọi số của B nằm trong `artifact/results/round3/summary.json`, đúng tên SCHEMA; renderer không ra `??` cho khóa của B
- [ ] Raw, PROTOCOL, EXCLUSIONS commit trước 29/11 (B7)
- [ ] Chế độ receiver ghi cho mọi lượt Device Farm
- [ ] Thay đổi hành vi `UpJob.onStopJob` (nếu có) ghi vào PROTOCOL
- [ ] Tài liệu cũ đã sửa (B8); rebuild độc lập có log (B9)
