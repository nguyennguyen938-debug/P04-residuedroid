# Việc cần điện thoại thật (B, round 3) — ghi lại, chưa chạy

Mọi việc khác của B chạy trên emulator hoặc trên Mac. Chỉ các mục dưới đây cần máy thật. Plan: `PLAN-ROUND3.md` (C11/B6,
Test 6), quyết định của B ngày 19/11 (RUNLOG).

| # | Việc | Vì sao cần máy thật | Cần gì trước | Ước chi phí | Hạn |
|---|---|---|---|---|---|
| 1 | **Test 1 rút gọn trên điện thoại** (phần còn thiếu của Test 6, C11) | race tự nhiên trên phần cứng/radio thật | B10 trên emulator (harness, thời gian mỗi trial); receiver chế độ B trên EC2 us-west-2 (tách receiver khỏi `tls_suite.py`, chứng chỉ SAN = IP EC2, cổng 8798, `tc` cho EDGE/3G/LTE); kiểm máy RTL ra được Internet tới EC2 | RTL ~8 credit; Device Farm ~120 phút (miễn phí còn 895); EC2 < 10 USD (user xác nhận lúc tạo) | 28/11 |
| 0 | **(DONE 19/11) Galaxy TLS v3** (sửa lỗi `concurrent`, `test6-card-v3.md`): `run_rtl.sh --tls-start 0 --tls-n 20 --tls-deadline-ms 60000 --out results/round3/test6/galaxy3-tls`, gói v5 | v2: hạn chờ cố định 10 s cắt `concurrent` trên relay chậm | gói v5 (đã có), phiên RTL ~30 phút | ~2 credit | sớm nhất có thể; Pixel v3 chạy trên Device Farm 19/11 |
| 2 | Galaxy v3 (tuỳ chọn): chạy lại toàn bộ TLS ×20 + lifecycle ×20 của Galaxy với receiver trên EC2 + log chẩn đoán job (`dumpsys jobscheduler`, `deviceidle`, standby bucket); báo cả v2 và v3 | v2 có `concurrent` 1/40 (relay chậm) và 2/60 trial không job nào chạy | receiver chế độ B (như #1) | RTL ~9–10 credit | 28/11, chỉ nếu còn credit sau #1 |

Quyết định đã chốt cho #1 (B, 19/11): máy chính Galaxy M35 trên RTL, thêm Pixel 8a trên Device Farm nếu còn phút; receiver
chế độ B trên EC2; giới hạn mạng bằng `tc` trên EC2; 3 profile EDGE/3G/LTE; 1 payload cỡ báo cáo ACRA; 2 biến thể paired
(layered early, fence); N chốt sau pilot B10 trên emulator, ghi trong card trước khi chạy.

Credit RTL còn ~9 (19/11): #0 ~2 credit (làm trước, rẻ), #1 ~8; #2 chỉ nếu còn credit.
Quy trình RTL: `plans/test6/README.md` (rtl_auto.sh fill mode, relay do Claude giữ, user bấm Remote Debug Bridge khi có NEED_CLICK).

## Trạng thái 19/11 23:00 (B)
- B10 trên emulator xong (protocol v3, `b10-card.md` §6): biết thời gian mỗi trial và tỷ lệ early/fence trên link đã giới hạn.
- Harness cho #1 sẵn sàng (chưa chạy): `race_suite.py --receiver http://IP:8800 --host IP --no-root --certdir <CA của EC2>`
  (receiver_b.py trên EC2 giới hạn băng thông bằng tc ingress/egress; log receiver tải về cuối lượt). API điều khiển đã thử cục
  bộ với `--no-tc` (profile, log, token sai → 403). Mặc định của race_suite không đổi.
- **Cần người dùng:** (1) đồng ý tạo EC2 (`plans/test6/ec2/setup.sh --create`, t3.micro us-west-2, < 10 USD, xoá bằng
  `teardown.sh` sau lượt); (2) một phiên RTL Galaxy M35 (~8 credit) và bấm Remote Debug Bridge khi được nhắc. Sau đó B chạy
  pilot (calibration 3 profile) → card `test1-phone-card.md` (N chốt sau pilot) → lượt chính.
- Quyết định người dùng 19/11 23:0x: #1 để sau, trước 28/11 (giữ trạng thái sẵn sàng; chưa tạo EC2).

## Quyết định người dùng 20/11 21:0x: không chạy #1 và #2
"test 1 trôi": Test 1 rút gọn trên điện thoại (#1) và Galaxy v3 qua EC2 (#2) không chạy; không tạo EC2, không dùng thêm credit
RTL. Test 1 chỉ có phần emulator (B10, `b10-card.md`); bài không có kết quả race trên radio/phần cứng thật (C11 phần Test 1 bỏ
trống — báo C). Thiếu beacon hợp lệ của Galaxy ở Test 6 v2 giữ là điểm chưa giải thích (mối đe dọa external). Harness remote
(`race_suite.py --receiver`) và `plans/test6/ec2/` giữ lại, không dùng.
