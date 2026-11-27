# Abstract đăng ký (A6, C6, nháp 18/11)

Hạn đăng ký: thứ Sáu 27/11 (AoE). Tác giả tự đăng ký, sớm hơn hạn một ngày (26/11). Mọi số trong abstract dưới đây chép từ `generated/macros.tex` và `generated/tests_macros.tex` ngày 24/11 (sau nhóm 3); trước khi bấm đăng ký, đối chiếu lại với hai file đó.

## Ba câu claim (A6)

1. **Lineage và epoch quyết định các lịch vòng đời.**
   - Trong fixture 10 tenant, các check thông thường để lọt dữ liệu theo ba cơ chế: bản tóm tắt nộp dưới scope khác (T1), dữ liệu cũ sau khi cấp lại đồng ý (T5), và đường retry sau khi job đã bắt đầu (T8).
   - Khi các check sớm nhận cùng metadata, layered early và fence đều có 0 vi phạm xác nhận, trên hai máy thuê và trên emulator Android 13, 14, 15.
2. **Chỗ đặt check chỉ quan trọng khi người dùng rút giữa lúc upload, và ranh giới là điểm commit W của lệnh rút.**
   - Mọi lệnh ghi sau W phải được kiểm lại dưới cùng khóa với lệnh rút.
   - Kết quả đo:
     - check đặt trước request để socket nhận byte sau ack ở 60,0% trial trên điện thoại (56,7% trên emulator);
     - trên Pixel 8a thuê (AWS), cancel từ process khác nhận lệnh ghi bắt đầu sau W ở 27/90 trial, cancel trong cùng process ở 6/90;
     - fence nhận 0.
   - Cancel trong cùng process là 0 trên emulator nhưng 6/90 trên máy thật, vì nó không serialize với writer.
   - Điểm hơn của fence là không cần registry các request đang bay.
3. **Bảo đảm có điều kiện, và bài nói rõ điều kiện.**
   - Cần mediation đầy đủ và nhãn đầy đủ: một nhãn hợp lệ nhưng thiếu nguồn vẫn lọt.
   - Dưới socket, khoảng một send buffer byte đã được nhận vẫn rời máy sau ack.
   - Ở phía server, khi buffer bằng nhau, cancel của HTTP client cho kết quả gần như fence.

Không đưa vào claim: "fence giữ được nhiều thư hợp lệ hơn". Phân tích C2 cho thấy mọi thư hợp lệ bị thiếu đều đến từ cách fixture xử lý reboot, không do chỗ đặt check.

## Abstract đăng ký (văn bản thuần, cập nhật 25/11: định vị lại claim theo R4 vòng 6)

Android apps persist outboxes and jobs that can outlive a user's withdrawal of consent. Enforcing the withdrawal is not only a matter of when to check a toggle: derived data must keep its source policy, and old data must stay distinguishable after consent is granted again. ResidueDroid keeps durable source epochs and labels with every persisted copy and job input, and checks the app's stated contract before each bounded socket write, serialized with withdrawal. We judge each workload against the contract it states. Lineage and epochs decide the lifecycle schedules: conventional checks fail through lost lineage, stale epochs and unchecked retries, while earlier checks that receive the same metadata show no confirmed violations, like the fence. Placement matters only when a withdrawal lands during an upload. A check before the request let the socket accept bytes after the acknowledgement in 60.0% of trials on a phone (56.7% on an emulator); on a rented phone, synchronously cancelling in-flight requests let none follow it, like the fence. They differ at the withdrawal's commit, after which the app's own policy state forbids the data: cancellation accepted newly started writes in 27 of 90 trials from another process and 6 of 90 from inside the sending process; the fence, which rechecks each write under the withdrawal's lock and needs no registry of in-flight requests, accepted none. Below the socket the designs converge: about one send buffer of accepted bytes still leaves the device. In a real app on a rented phone, the stock build shared opt-out data after re-consent in 40 of 40 trials, the fenced and layered builds in none. The guarantee requires complete mediation and complete labels.

## Tác giả (thứ tự người dùng chốt ngày 27/11, giống `main.tex`)

Ngày 27/11: bỏ Khang; thêm Phat T. Tran-Truong và Xuan Son Ha trước thầy Bách. Email, đơn vị và ORCID của hai người mới lấy từ bài ICSOC 2026 (QuantumTrustKG) mà người dùng gửi.

Đơn vị: (1) Ho Chi Minh City University of Technology (HCMUT), VNU-HCM, Vietnam; (2) RMIT University, Vietnam.

| # | Tên in | Đơn vị | Email | ORCID |
|---|---|---|---|---|
| 1 | Nhat Duy Nguyen | 1 | duy.nguyencse@hcmut.edu.vn | 0009-0003-5543-8181 |
| 2 | Phung Trung Nguyen Nguyen | 1 | nguyen.nguyen938@hcmut.edu.vn | 0009-0004-8643-4172 |
| 3 | Dang Nghia Nguyen (đổi thứ tự tên 28/11, khớp HotCRP) | 1 | nghia.nguyen3112007@hcmut.edu.vn (lấy từ git commit, cần Nghĩa xác nhận) | chưa có |
| 4 | Hieu Le Minh | 1 | hieu.lehieulhks@hcmut.edu.vn | 0009-0003-9199-7677 |
| 5 | Phat T. Tran-Truong | 1 | phatttt@hcmut.edu.vn | 0000-0003-3199-6333 |
| 6 | Xuan Son Ha | 2 | ha.son@rmit.edu.vn | 0000-0002-5336-0566 |
| 7 | Xuan-Bach Le (corresponding) | 1 | lexuanbach@hcmut.edu.vn | 0009-0003-6848-5403 |

## Cần kiểm trước khi bấm đăng ký

- Tên bài, danh sách tác giả, topic trên HotCRP.
- Các số 60.0, 56.7, 27/90, 6/90, 40/40 còn khớp với `generated/` không (macro: racePhoneObsPct, raceObsPct, dfCloseAll/dfArmN, dfCloseTwoAll, dfAirStockPK/dfAirPKN, dfAirFence, dfAirLayer).
- Không có dấu gạch ngang dài trong văn bản.
