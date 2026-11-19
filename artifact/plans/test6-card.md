# Experiment card — test6 (protocol v2)

Status: protocol v2 (v1 frozen 7b2b523; v2 = v1 + Device Farm spec change after pilot-df-pixel8a, see §3 "Pilots"); frozen-test6-v2 trước lượt chính
Owner (experimenter): B (Duy)   Approved by (author): C đồng ý môi trường RTL (19/11, theo lời user); định nghĩa khóa §4 chờ C

Nguồn: `[R3]` = `PLAN-ROUND3.md`, `[HB]` = `HUONG-DAN-B.md`, `[DF]` = `artifact/devicefarm/README.md`, `[RT]` =
`artifact/scripts/render_tests.py` (SCHEMA), `[T6]` = `artifact/plans/test6/README.md`, RUNLOG 18–19/11. Chỗ plan không nói
ghi *plan không nêu*; chỗ nào chưa chốt thì là việc phải hỏi trước khi chạy.

## 1. Question and claim
- Câu hỏi: trên điện thoại thật, không root, cơ chế barrier/backpressure TLS và hành vi lifecycle không reboot (pen, kill,
  rev) của các biến thể matched có giống những gì đã quan sát trên emulator không? Trả lời R1, R3 [R3 §Sáu test].
- Claim có thể đỡ (phạm vi hẹp): "Trên hai điện thoại thật khác hãng và khác bản Android (Pixel 8a Android 17 qua AWS Device
  Farm; Galaxy M35 Android 14 qua Samsung Remote Test Lab), trong N trial hợp lệ, quan sát được …" kèm tử số/mẫu số và CI.
- Claim không đỡ: hành vi chung của OEM/hãng; năng lượng; triển khai thật; đường mạng thật (receiver qua `adb reverse`);
  reboot và mất mạng trên điện thoại (chỉ emulator, [R3 §Rủi ro]); test 1 trên máy thật (chưa làm, cần receiver EC2, [DF]);
  hai máy không phải nhân bản độc lập phần cứng; app bất kỳ (chỉ fixture ResidueLab).
- Nơi dùng: §7a (C viết). Khóa `summary.json` [RT]: `devModel`, `devAndroid`, `devTrials`, `devEarlyComplete`,
  `devFenceAfterAck`. Lifecycle trên điện thoại: **chưa có khóa** (C thêm hoặc chỉ để raw/appendix). Dòng ledger
  `others/notes.md`: C thêm khi viết.

## 2. Design
- Thiết bị (chốt 19/11): **P** = Pixel 8a, Android 17, AWS Device Farm (receiver chế độ A: host Device Farm qua `adb reverse`/USB);
  **G** = Galaxy M35 SM-M356B, Android 14, Samsung RTL qua Remote Debug Bridge (receiver trên Mac qua `adb reverse` đi qua relay
  RDB). Nếu RTL không còn SM-M356B Android 14: dừng, hỏi, không tự đổi máy.
- TLS: `followup/tls_suite.py --no-root --host 127.0.0.1`, 7 case cố định thứ tự `control, early, buffered-fence,
  buffered-early, stall-small, stall-large, concurrent` [DF testspec]; 1 block = 1 lượt 7 case.
- Lifecycle: `followup/campaign.py --no-root --sink-host 127.0.0.1 --port 8787`, biến thể matched `menqueue, mstart, mlayer,
  mfence, mboth`, `--timeout 90`, `--apkdir fixture/build/revision-apk` (như `followup/start_matched.py`); lịch `pending, kill,
  revoke` theo thứ tự cố định trong mỗi block k (không ngẫu nhiên hoá: harness lặp k ngoài, lịch trong). 5 biến thể chạy
  trong cùng một trial (paired).
- Đơn vị phân tích: TLS = trial (case × block), chọn theo block; lifecycle = paired trial (5 biến thể cùng trial), tenant
  bị ảnh hưởng 1, 2, 4, 5, 8 như `matched_oracle.py`.
- **N = 20** mỗi ô (user, 19/11): TLS 20 block hợp lệ mỗi máy; lifecycle 20 paired trial hợp lệ mỗi lịch mỗi máy.
- Seed: `test6-20261119` (cả hai máy; với pen/kill/rev seed không dùng trong lịch, ghi để đủ). Pilot dùng `test6-pilot`.
- Chia lượt (thời gian đo ở pilot-rtl-3: TLS 36 s/block, lifecycle 75–99 s/trial):

  | Máy | Lượt | Nội dung | Thư mục |
  |---|---|---|---|
  | P | pilot | `testspec-pilot-combined.yml`: TLS 1 block + 1 trial mỗi lịch, timeout job 20 phút | `pilot-df-pixel8a` (pilot, loại khỏi phân tích) |
  | P | job 1 | `testspec-main-job1.yml`: TLS block 0–19 + lifecycle k 0–9, timeout 100 phút | `pixel8a-j1` |
  | P | job 2 | `testspec-main-job2.yml`: lifecycle k 10–19, timeout 100 phút | `pixel8a-j2` |
  | G | phiên 1 (60 phút) | `run_rtl.sh --tls-start 0 --tls-n 20 --life-start 0 --life-trials 5` | `galaxy-s1` |
  | G | phiên 2–4 (45 phút) | `--life-start 5/10/15 --life-trials 5` | `galaxy-s2`…`s4` |

  Ngân sách: P ≈ 150 phút Device Farm (tối đa 220) trong 1.000 phút dùng thử; G ≈ 13 credit RTL (4 + 3×3) trong 22.
- Build: gói v4 (zip sha256 `8562abeb…09d7`) = HEAD của `b-exp` sau commit card này; APK fixture build từ `400f62e`, nguồn
  fixture không đổi đến nay (đã kiểm `git diff`); `package-sha256.json` (RTL) và `environment.json` (TLS) ghi hash APK đã cài.
  Freeze trước lượt chính đầu tiên: `python3 artifact/revision/freeze.py artifact/results/round3/test6/frozen-test6-v1`
  (freeze.py không gồm `followup/`) + `package-sha256.json` của gói v4 (mọi file trừ `test-key.pem`) và sha256 của zip,
  cùng thư mục.
- RTL: adb platform-tools **r33.0.3** trên server port riêng 5038 (adb 37 treo với RDB); không bao giờ mở shell dưới `run-as`
  (làm chết RDB; RUNLOG 08:44). Script `plans/test6/run_rtl.sh` kiểm trước khi cài (model, Android, uid shell, run-as,
  reverse), probe đường nối mỗi 2 s, dừng harness khi mất 6 probe liên tiếp, luôn dọn (gỡ app, xoá reverse, tắt listener).
- Cửa sổ quan sát: lifecycle chờ tới khi không còn job của mình hoặc 90 s (backstop force-run sau 60 s); TLS chờ barrier 5 s,
  kết thúc request 13 s (như `tls_suite.py`).

## 3. Validity, exclusion, stopping, replacement (cố định trước lượt chính)
- TLS trial không hợp lệ nếu: có `harness_error`; hoặc case buffered/stall mà `barrier_seen` không phải true. Block hợp lệ khi
  đủ 7 case và cả 7 hợp lệ. Phân tích 20 block hợp lệ đầu tiên theo số block; còn lại là unused (vẫn báo).
- Lifecycle paired trial không hợp lệ nếu (quy tắc của `followup/matched_oracle.py`, giữ nguyên): có `trial_error`,
  `setup_fail` hoặc `emulator_restarted`; khoảng cách giữa hai action > 200 s; thiết bị không sống lúc cuối; thiếu log của một
  biến thể. Thêm cho điện thoại: lịch kill mà `kill_verified` không true; `seen_max` ≤ 0 (không parse được job nào của mình
  trong lúc chờ). Phân tích 20 trial hợp lệ đầu tiên theo k mỗi (máy, lịch).
- Các quy tắc đọc trường harness/fault, không đọc kết quả (sink, vi phạm). Code: `followup/analyze_test6.py`, test
  `followup/test_analyze_test6.py`.
- Lỗi môi trường được ghi: RDB mất (`LINK_DOWN`, exit 4), job Device Farm timeout/lỗi, phiên RTL hết giờ, thiết bị không trả lời.
- Thay thế (chỉ cho lỗi môi trường, ghi RUNLOG): TLS → block mới số ≥ 20 (`--start 20…`); lifecycle → trial cùng lịch với k mới
  ≥ 20, chạy trong thư mục mới (RTL: phiên thêm hoặc phần thời gian còn lại; P: job 3 sinh từ job 2 chỉ đổi `--start/--trials
  /--schedules`). Trần: 5 block TLS và 5 trial mỗi lịch mỗi máy; không thay vì kết quả.
- Dừng: khi đủ các lượt ở §2 và các thay thế cần thiết, hoặc chạm trần thay thế/ngân sách (RTL 22 credit, Device Farm 1.000
  phút) → báo số N thực có. Không kéo dài, không lặp, không bỏ trial vì kết quả.
- Cổng pilot P (cơ chế, không xem kết quả): TLS_EXIT=0, 7/7 trial, `barrier_seen` true ở 4 case barrier, receiver có dòng;
  LIFE_EXIT=0, 3/3 trial, `remaining` 0, `seen_max` > 0 (Android 17 có thể đổi định dạng `dumpsys jobscheduler`),
  `kill_verified` true, không lỗi đọc DB, sink có dòng, `device_alive_end` true; thời gian job để chỉnh timeout. Không đạt →
  sửa, pilot lại, protocol v2. Với G: phiên 1 dừng ngay nếu trial đầu có `seen_max` ≤ 0 hoặc `kill_verified` false.
- Pilot đã có (loại khỏi phân tích): `pilot-local-1/2` (emulator), `pilot-rtl-1/2` (hỏng do `run-as sh` làm chết RDB),
  `pilot-rtl-3` (đạt). Thay đổi do pilot: CA copy bằng `run-as tee` (`tls_suite.py:56`), `--start` cho TLS, `seen_max`.
  `pilot-df-pixel8a` (v1, Pixel 8a Android 17): lifecycle đạt mọi cổng (`seen_max` 65–67); TLS không chạy trial nào vì
  `adb install -r rl-tls.apk` thất bại (Device Farm đã cài sẵn app này làm app under test; adb 1.0.39). **v2:** `pre_test` của
  các spec Device Farm in installer/update owner của `org.residuelab.tls` rồi gỡ nó, để `tls_suite.py` cài lại như trên RTL.
  Harness, phân tích, N và quy tắc không đổi. Pilot lại: `pilot-df-pixel8a-2`.

## 4. Analysis
- Script: `followup/analyze_test6.py --manifest plans/test6/runs.json` → `results/round3/test6/analysis/`. Lifecycle dùng
  nguyên code `followup/matched_oracle.py` (chỉ thay chỗ đọc/ghi và danh sách run, có assert); TLS theo công thức hàng của
  `followup/analyze_tls.py` nhưng không assert.
- Estimand lifecycle: tỉ lệ tenant bị ảnh hưởng có vi phạm được xác nhận, mỗi biến thể; request unknown báo riêng (không gộp
  vào "không vi phạm"); hiệu paired sớm-vs-fence; deficit hợp lệ. Biên quan sát: `WRITE_ATTEMPT` + `BYTES_ACCEPTED.n` + thứ
  tự giao dịch withdrawal trên máy (như matched campaign).
- TLS mỗi case: số trial, request gửi xong, trial bị chặn, trial có byte được nhận sau ack (+ Wilson 95%).
- **Định nghĩa khóa đề xuất, chờ C xác nhận trước lượt chính** [RT chỉ có mô tả ngắn]: `devModel` = tên máy (P, G);
  `devAndroid` = bản Android (P, G); `devTrials` = số trial phân tích ở `buffered-fence` + `buffered-early`, cộng hai máy;
  `devEarlyComplete` = số request `SEND_OK` trong trial `buffered-early`; `devFenceAfterAck` = số trial fence (`buffered-fence`,
  `stall-small`, `stall-large`) có byte được nhận sau ack, mẫu số `devFenceTrials`. Nếu C muốn tách theo máy thì sửa trước.
- Bất định: Wilson 95% cho tỉ lệ; lifecycle: bootstrap cả paired trial trong `matched_oracle.py`, phân tầng (lịch × lượt/phiên),
  10.000 lần, seed 20261115. Tầng chỉ có 1 trial không ước được biến thiên trong tầng.
- Output: `results/round3/test6/analysis/test6-summary.json` (+ `matched-*.json`); B ghi `summary.json` sau khi C chốt định nghĩa.

## 5. Threats to validity
- Internal: thứ tự cố định (case TLS, lịch trong block); hai máy chạy ở thời điểm/ngày khác nhau và môi trường khác (host
  Device Farm vs Mac + relay RDB); trễ relay thay đổi; harness đọc DB qua `run-as` thay vì root (đã kiểm byte-identical).
- Construct: socket của app kết thúc ở `adbd` trên máy (cả hai chế độ đều qua `adb reverse`), nên barrier/backpressure đo
  việc socket trên máy nhận byte, không đo đường mạng [DF]; accepted bytes ≠ receipt ≠ xử lý ở server.
- External: 2 máy, mỗi model 1 chiếc, máy thuê, đang cắm sạc (không tự vào Doze); Android 17 và 14; fixture, không phải app
  thật; reb/net chỉ ở emulator.
- Conclusion: N = 20 mỗi ô; phân tầng theo lượt/phiên; nhiều so sánh (5 biến thể × 3 lịch × 2 máy) chỉ mô tả, không p-value;
  zero-vs-zero báo số đếm paired.

## 6. Outcome (điền sau khi chạy, không sửa phần trên)
- Logged / excluded by reason / valid / analyzed / unused (19/11, `followup/analyze_test6.py`): TLS mỗi máy 20 block logged,
  0 invalid, 20 valid, 20 analyzed, 0 unused. Lifecycle mỗi máy mỗi lịch (pending, kill, revoke) 20 paired trial logged, 0 invalid
  (cả quy tắc oracle lẫn quy tắc điện thoại), 20 analyzed, 0 unused. Không cần thay thế. Lượt hỏng/pilot giữ lại, không phân
  tích: `pilot-*`, `galaxy-s1_INVALID_rdb-connect`, `_rdb-connect2`, `_rdb-noanswer`, `galaxy-p01_INVALID_relpath` (không trial nào).
- Results directory: `results/round3/test6/` — P: `pixel8a-j1`, `pixel8a-j2`; G: `galaxy-s1`, `galaxy-p02`, `galaxy-p03`;
  phân tích `analysis/` (`test6-summary.json`, `matched-*.json`).
- Deviations: (1) protocol v2 trước lượt chính (gỡ app TLS cài sẵn trong spec Device Farm). (2) Chia lượt G khác §2: s1 = TLS 0–19
  + k 0–1 (phiên chỉ còn 37 phút), sau đó chế độ fill: p02 = k 2–17, p03 = k 18–19; N, quy tắc, lệnh harness không đổi.
  (3) Job 1 của P được tải về bằng `fetch_df.sh` sau khi poller chết (sửa script khi đang chạy); dữ liệu đủ. (4) Định nghĩa khóa
  `summary.json` §4 vẫn chờ C; `summary.json` chưa ghi.
- Negative or null results: G `concurrent`: 39/40 request kết thúc `SEND_ERROR` (26 TLS deadline, 10 process lock deadline,
  2 policy lock deadline), P 40/40 `SEND_OK`; trial hợp lệ theo quy tắc (không harness_error); khả năng do đường receiver qua relay
  RDB tới Mac (chưa kiểm chứng) → mối đe dọa construct/external, báo cả hai máy. G: deficit hợp lệ (`legit_missing`) khác 0 ở mọi
  biến thể, P bằng 0 (trừ mstart ở cả hai) — báo nguyên số trong `matched-summary.json`, không diễn giải thêm ở đây.
