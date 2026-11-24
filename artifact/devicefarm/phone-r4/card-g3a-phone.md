# Experiment card (NHÁP của C): G3a trên điện thoại cá nhân (protocol v1)

Status: draft (C soạn 24/11; B sửa, chép sang `plans/g3a-phone-card.md` và commit trước lượt final)
Owner (experimenter): B (Duy)   Approved by (author): chờ leader

## 1. Question and claim
- Câu hỏi: trên điện thoại thật, socket có nhận lệnh ghi bắt đầu sau điểm commit W của lệnh rút không, ở 5 arm của G3a
  (early, cancel khác process `close`, cancel cùng process `close2`, fence, fence abortive)?
- Claim đỡ được: Table commit của paper lặp lại (hoặc không) trên một điện thoại Android 15 với link đã giới hạn ở receiver.
- Claim không đỡ được: các hãng/máy khác; đường vô tuyến thật không giới hạn; byte rời máy sau ack (không có capture).
- Chỗ trong paper: §7.3 (Table commit, thêm cột máy thật), abstract nếu kết quả khác emulator. Dòng sổ claim mới.

## 2. Design
- Arm: `early, close, close2, fence, fence-abort`, chung block, cùng `u` theo (block, profile, size) như G3a.
- Profile: edge, umts, lte (receiver_b `PROFILE_SET=b10v3`, giới hạn chiều upload ở EC2, như Test 1 trên máy này).
- Size: 32 KiB, 256 KiB, 2 MiB. `--sndbuf 16384` như G3a. `--warm-revision` như P3 (process `:revision` khởi động trước mọi arm).
- Đơn vị: trial. Mỗi block = 5 arm × 3 profile × 3 size = 45 trial, thứ tự xáo theo block.
- N: số block theo quy tắc pilot (`run_g3a_phone.sh pilot`): `min(10, floor(300 phút / cận trên thời gian một block))`;
  dưới 5 block thì không chạy final. Ghi N vào card trước khi chạy final.
- Seed: `g3a-phone-20261125`.
- Thiết bị: điện thoại cá nhân (model/Android ghi từ meta.json; không ghi serial). Receiver EC2 (`plans/test6/ec2/`).
- Build: `fixture/build/g3-apk/rl-tls.apk` (bản G3a); freeze `results/round3/phone-r4/g3a/frozen-g3a-phone`.
- Cửa sổ: deadline như race_suite (`max(10 s, 4D + 20 s)`).

## 3. Validity, exclusion, stopping, replacement
- Trial không hợp lệ: theo `analyze_g3race.py` (harness_error, thiếu event kết thúc), như G3a.
- Dừng: sau N block. Không dừng hay chạy thêm theo kết quả.
- Thay thế: chỉ lỗi môi trường (mất adb, EC2 mất kết nối), cả block, chạy tiếp vào `final-r2` với `--start` (như G3a).
- Pilot: `pilot-calib-*` (fence, không rút), loại khỏi phân tích; cổng = các profile tách nhau (edge ≥ 3×lte, umts ≥ 1,5×lte).

## 4. Analysis
- `followup/analyze_g3race.py results/round3/phone-r4/g3a/final --n 3N` (không đổi).
- Primary (như G3a): số trial có `BYTES_ACCEPTED n>0` mà `WRITE_ATTEMPT` gần nhất sau W, theo arm và profile; Wilson 95%.
- Phụ: trial nhận byte sau ack; độ trễ ack (median, p95).
- Key mới cho paper: C thêm (`gtrPhone*`), báo cạnh số emulator, không thay.

## 5. Threats
- Internal: receiver ở xa (độ trễ mạng thật cộng giới hạn); process `:revision` có thể bị đóng băng trên Android 15.
- Construct: chỉ đo ở mức socket acceptance; không đo byte rời máy.
- External: một máy, một mạng.
- Conclusion: N nhỏ hơn G3a nếu pilot cho block dài; 0 trên N không phải bảo đảm.

## 6. Outcome (điền sau khi chạy)
