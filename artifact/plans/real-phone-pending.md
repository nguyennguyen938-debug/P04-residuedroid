# Việc cần điện thoại thật (B, round 3) — ghi lại, chưa chạy

Mọi việc khác của B chạy trên emulator hoặc trên Mac. Chỉ các mục dưới đây cần máy thật. Plan: `PLAN-ROUND3.md` (C11/B6,
Test 6), quyết định của B ngày 19/11 (RUNLOG).

| # | Việc | Vì sao cần máy thật | Cần gì trước | Ước chi phí | Hạn |
|---|---|---|---|---|---|
| 1 | **Test 1 rút gọn trên điện thoại** (phần còn thiếu của Test 6, C11) | race tự nhiên trên phần cứng/radio thật | B10 trên emulator (harness, thời gian mỗi trial); receiver chế độ B trên EC2 us-west-2 (tách receiver khỏi `tls_suite.py`, chứng chỉ SAN = IP EC2, cổng 8798, `tc` cho EDGE/3G/LTE); kiểm máy RTL ra được Internet tới EC2 | RTL ~8 credit; Device Farm ~120 phút (miễn phí còn 895); EC2 < 10 USD (user xác nhận lúc tạo) | 28/11 |
| 0 | **Galaxy TLS v3** (sửa lỗi `concurrent`, `test6-card-v3.md`): `run_rtl.sh --tls-start 0 --tls-n 20 --tls-deadline-ms 60000 --out results/round3/test6/galaxy3-tls`, gói v5 | v2: hạn chờ cố định 10 s cắt `concurrent` trên relay chậm | gói v5 (đã có), phiên RTL ~30 phút | ~2 credit | sớm nhất có thể; Pixel v3 chạy trên Device Farm 19/11 |
| 2 | Galaxy v3 (tuỳ chọn): chạy lại toàn bộ TLS ×20 + lifecycle ×20 của Galaxy với receiver trên EC2 + log chẩn đoán job (`dumpsys jobscheduler`, `deviceidle`, standby bucket); báo cả v2 và v3 | v2 có `concurrent` 1/40 (relay chậm) và 2/60 trial không job nào chạy | receiver chế độ B (như #1) | RTL ~9–10 credit | 28/11, chỉ nếu còn credit sau #1 |

Quyết định đã chốt cho #1 (B, 19/11): máy chính Galaxy M35 trên RTL, thêm Pixel 8a trên Device Farm nếu còn phút; receiver
chế độ B trên EC2; giới hạn mạng bằng `tc` trên EC2; 3 profile EDGE/3G/LTE; 1 payload cỡ báo cáo ACRA; 2 biến thể paired
(layered early, fence); N chốt sau pilot B10 trên emulator, ghi trong card trước khi chạy.

Credit RTL còn ~9 (19/11): #0 ~2 credit (làm trước, rẻ), #1 ~8; #2 chỉ nếu còn credit.
Quy trình RTL: `plans/test6/README.md` (rtl_auto.sh fill mode, relay do Claude giữ, user bấm Remote Debug Bridge khi có NEED_CLICK).
