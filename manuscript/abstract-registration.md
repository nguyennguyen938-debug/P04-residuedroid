# Abstract đăng ký (A6, C6, nháp 18/11)

Hạn đăng ký: thứ Sáu 27/11 (AoE). Tác giả tự đăng ký, sớm hơn hạn một ngày (26/11). Mọi số dưới đây lấy từ `generated/macros.tex` và các file generated; chưa có số nào từ 6 test mới. Có kết quả mới thì C7 cập nhật trước khi nộp bài (4/12).

## Ba câu claim (A6)

1. **Bài toán là lineage và epoch, không chỉ là chọn chỗ đặt check.** Trong fixture 10 tenant, các check thông thường để lọt dữ liệu theo ba cơ chế khác nhau: bản tóm tắt nộp dưới scope khác (T1), dữ liệu cũ sau khi cấp lại đồng ý (T5), và đường retry sau khi job đã bắt đầu (T8).
2. **Khi các check sớm nhận cùng metadata, fence chỉ hơn ở một race hẹp.** Trong 280 paired trial mỗi biến thể, qua 7 lịch vòng đời, cả layered early lẫn fence đều có 0 vi phạm xác nhận. Lợi thế của fence nằm ở khe giữa check và lệnh ghi: với barrier TLS, check sớm hoàn tất 20/20 request, còn fence không cho socket nhận byte ciphertext nào sau acknowledgement.
3. **Bảo đảm có điều kiện, và bài nói rõ điều kiện.** Cần mediation đầy đủ và nhãn đầy đủ. Một nhãn hợp lệ nhưng thiếu nguồn vẫn lọt 20/20. Byte đã handoff trước khi rút vẫn có thể tới receiver.

Không đưa vào claim: "fence giữ được nhiều thư hợp lệ hơn". Phân tích C2 cho thấy mọi thư hợp lệ bị thiếu đều đến từ cách fixture xử lý reboot, không do chỗ đặt check.

## Abstract đăng ký (văn bản thuần, khoảng 180 từ)

Android apps persist outboxes and jobs that can outlive a user's withdrawal of consent. Enforcing the withdrawal is not only a matter of when to check a toggle: derived data must keep its source policy, and old data must stay distinguishable after consent is granted again. ResidueDroid combines durable per-source epochs, labels stored with every persisted copy and job input, and a policy check serialized with each bounded socket write. We separate collection-only opt-outs, processing restrictions and deletion requests, and judge each workload against the contract it states. A 360-app static screen identifies candidate deferred paths, not violations. In controlled emulator experiments, conventional checks fail through lineage loss, stale epochs and unchecked retries. When earlier checks receive the same metadata, they show no confirmed violation in 280 paired trials per variant; the late fence closes a narrower race, which a TLS buffering barrier exposes in 20 of 20 early-check trials and in none with the fence. ACRA and Matomo embeddings exercise real queued-report and dispatcher paths. The guarantee requires complete mediation and complete labels, and bytes accepted before withdrawal can still arrive.

## Cần kiểm trước khi bấm đăng ký

- Tên bài, danh sách tác giả, topic trên HotCRP.
- Số 360, 280, 20/20 còn khớp với `generated/` không (chạy lại render nếu B có dữ liệu mới).
- Không có dấu gạch ngang dài trong văn bản.
