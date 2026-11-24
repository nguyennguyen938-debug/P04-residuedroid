# Abstract đăng ký (A6, C6, nháp 18/11)

Hạn đăng ký: thứ Sáu 27/11 (AoE). Tác giả tự đăng ký, sớm hơn hạn một ngày (26/11). Mọi số trong abstract dưới đây chép từ `generated/macros.tex` và `generated/tests_macros.tex` ngày 24/11 (sau nhóm 3); trước khi bấm đăng ký, đối chiếu lại với hai file đó.

## Ba câu claim (A6)

1. **Lineage và epoch quyết định các lịch vòng đời.**
   - Trong fixture 10 tenant, các check thông thường để lọt dữ liệu theo ba cơ chế: bản tóm tắt nộp dưới scope khác (T1), dữ liệu cũ sau khi cấp lại đồng ý (T5), và đường retry sau khi job đã bắt đầu (T8).
   - Khi các check sớm nhận cùng metadata, layered early và fence đều có 0 vi phạm xác nhận, trên Android 13, 14 và 15.
2. **Chỗ đặt check chỉ quan trọng khi người dùng rút giữa lúc upload, và ranh giới là điểm commit W của lệnh rút.**
   - Mọi lệnh ghi sau W phải được kiểm lại dưới cùng khóa với lệnh rút.
   - Kết quả đo:
     - check đặt trước request để socket nhận byte sau ack ở 56,7% trial emulator và 60,0% trên điện thoại;
     - cancel từ process khác vẫn nhận lệnh ghi bắt đầu sau W ở 8/90 trial;
     - fence nhận 0.
   - Cancel trong cùng process cũng 0, nhưng nó không serialize với writer, nên số 0 này không phải bảo đảm.
   - Điểm hơn của fence là không cần registry các request đang bay.
3. **Bảo đảm có điều kiện, và bài nói rõ điều kiện.**
   - Cần mediation đầy đủ và nhãn đầy đủ: một nhãn hợp lệ nhưng thiếu nguồn vẫn lọt.
   - Dưới socket, khoảng một send buffer byte đã được nhận vẫn rời máy sau ack.
   - Ở phía server, khi buffer bằng nhau, cancel của HTTP client cho kết quả gần như fence.

Không đưa vào claim: "fence giữ được nhiều thư hợp lệ hơn". Phân tích C2 cho thấy mọi thư hợp lệ bị thiếu đều đến từ cách fixture xử lý reboot, không do chỗ đặt check.

## Abstract đăng ký (văn bản thuần, cập nhật 24/11: nhóm 3 và claim viết lại)

Android apps persist outboxes and jobs that can outlive a user's withdrawal of consent. Enforcing the withdrawal is not only a matter of when to check a toggle: derived data must keep its source policy, and old data must stay distinguishable after consent is granted again. ResidueDroid keeps durable source epochs and labels with every persisted copy and job input, and checks the app's stated contract before each bounded socket write, serialized with withdrawal. We judge each workload against the contract it states. Lineage and epochs decide the lifecycle schedules: conventional checks fail through lost lineage, stale epochs and unchecked retries, while earlier checks that receive the same metadata show no confirmed violations, like the fence. Placement matters only when a withdrawal lands during an upload, where every write after the withdrawal commits must be rechecked under its lock: a check before the request let the socket accept bytes afterwards in 56.7% of emulator trials and 60.0% on a phone, and cancellation from another process still accepted writes started after the commit in 8 of 90 trials; the fence accepted none. Below the socket the designs converge: about one send buffer of accepted bytes still leaves the device. In a real app, the stock build shares opt-out data after re-consent in 60 of 60 trials; the fenced build has no confirmed violation, with 26 trials unknown under the pre-registered oracle. The guarantee requires complete mediation and complete labels.

## Tác giả (thứ tự người dùng chốt ngày 24/11, giống `main.tex`)

Đơn vị chung: Ho Chi Minh City University of Technology (HCMUT), VNU-HCM, Vietnam.

| # | Tên in | Email | ORCID |
|---|---|---|---|
| 1 | Nhat Duy Nguyen | duy.nguyencse@hcmut.edu.vn | 0009-0003-5543-8181 |
| 2 | Phung Trung Nguyen Nguyen | nguyen.nguyen938@hcmut.edu.vn | 0009-0004-8643-4172 |
| 3 | Nguyen Dang Nghia | nghia.nguyen3112007@hcmut.edu.vn (lấy từ git commit, cần Nghĩa xác nhận) | chưa có |
| 4 | Hieu Le Minh | hieu.lehieulhks@hcmut.edu.vn | 0009-0003-9199-7677 |
| 5 | Nguyen Hoang Nhat Khang | khang.nguyen2111@hcmut.edu.vn | 0009-0008-2781-7228 |
| 6 | Xuan-Bach Le (corresponding) | lexuanbach@hcmut.edu.vn | 0009-0003-6848-5403 |

## Cần kiểm trước khi bấm đăng ký

- Tên bài, danh sách tác giả, topic trên HotCRP.
- Các số 56.7, 60.0, 8/90, 60/60, 26 còn khớp với `generated/` không (macro: raceObsPct, racePhoneObsPct, gtrCloseW/gtrN, airStockViol/airN, airFenceUnknownV).
- Không có dấu gạch ngang dài trong văn bản.
