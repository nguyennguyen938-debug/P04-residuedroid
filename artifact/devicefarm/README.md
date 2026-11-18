# Test 6 trên điện thoại thật qua AWS Device Farm (C11, bản chuẩn bị)

Chỉ dùng khi buổi S0 chọn đường 2 (thuê AWS). Nếu mua máy thì B cắm máy vào Mac và dùng cùng `real-device.patch`, bỏ qua phần Device Farm.

## Chạy được gì

| Phần | Trạng thái |
|---|---|
| TLS barrier (`buffered-early`, `buffered-fence`), backpressure (`stall-small`, `stall-large`), `control`, `early`, `concurrent` của `followup/tls_suite.py` | Chạy được sau khi áp `real-device.patch` |
| Lifecycle (pen, kill, rev) của fixture | **Chưa.** `Fence.HOST` của fixture ghi cứng `10.0.2.2`, và harness `followup/campaign.py` đọc log app bằng `sqlite3` dưới quyền root. Cả hai phải sửa trước |
| Reboot, cắt mạng | Chưa biết Device Farm có cho không; kiểm ở lượt chạy thử |

## Bốn chỗ chặn khi chạy trên máy thật (đã gói thành `real-device.patch`)

Patch chạm vào file của B (`fixture/src/.../Revision.java`, `followup/tls_suite.py`), nên B xem và áp, không commit thẳng.

1. App gửi tới `10.0.2.2` (địa chỉ host chỉ có trên emulator). Patch thêm extra `host`, mặc định vẫn là `10.0.2.2`.
2. Harness gọi `adb root`, máy thật không cho. Patch thêm cờ `--no-root`. `run-as` vẫn chạy vì APK có `android:debuggable="true"`.
3. Harness dùng đường dẫn adb của SDK trên Mac. Patch cho phép đặt qua biến môi trường `ADB`.
4. Đọc `/proc/net/tcp` sau khi rút có thể bị từ chối trên máy thật. Patch ghi lại lỗi thay vì làm hỏng cả trial.

Đã kiểm ở đây: patch áp sạch vào source gốc (`git apply --check`), và `tls_suite.py` sau khi áp vẫn biên dịch được. **Chưa chạy trên thiết bị nào.**

## Receiver

- **Chế độ A (đang dùng trong `testspec.yml`):** receiver chạy ngay trên máy host của Device Farm; điện thoại tới đó qua `adb reverse`, tức là qua USB. Chứng chỉ test hiện có đã có SAN `127.0.0.1`. Đủ cho barrier và backpressure, vì hai phép đo này nói về lúc socket nhận byte, không nói về đường mạng.
- **Chế độ B (cần cho test 1 trên máy thật):** receiver trên một máy EC2 cùng vùng `us-west-2`, điện thoại đi qua mạng thật. Phải tách phần receiver của `tls_suite.py` ra chạy trên EC2, tạo lại chứng chỉ có SAN là IP của EC2, mở cổng 8798. Chưa làm.

Trong §7a phải ghi rõ chế độ nào đã dùng.

## Các bước

1. S0 chọn đường 2. Người dùng tự tạo tài khoản AWS và bật thanh toán; kiểm trên trang giá xem còn 1.000 phút dùng thử không.
2. B áp `real-device.patch`, build `fixture/build/tls-apk/rl-tls.apk`, tạo cặp chứng chỉ test theo `followup/tls-cert/README.md`.
3. Đóng gói zip gồm `artifact/followup/tls_suite.py`, `artifact/followup/tls-cert/` (có cả `test-key.pem`, đây chỉ là khóa test), `artifact/fixture/build/tls-apk/rl-tls.apk`, giữ đúng đường dẫn tương đối. Kiểm loại test package nào của Device Farm cho chạy custom environment với script Python.
4. **Chạy thử** một máy, `--n 1`. Kiểm: `adb root` bị từ chối nhưng không làm hỏng lượt chạy; `run-as` đọc được `revision.jsonl`; `barrier_seen` là true; receiver nhận đủ request `control`.
5. Chạy thật: hai máy khác hãng (một Pixel, một Samsung), `--n 20`.

## Chi phí ước tính

Mỗi trial mất khoảng 15 giây (force-stop, khởi tạo, gửi, chờ tối đa 13 giây). 7 case × 20 block = 140 trial, khoảng 35 phút mỗi máy. Hai máy và một lượt chạy thử khoảng 100 phút, chừng 17 USD theo giá 0,17 USD mỗi phút. Nếu còn 1.000 phút dùng thử thì không mất tiền. Con số này thấp hơn ước lượng 1.100 phút trong plan, vì chưa gồm test 1 và lifecycle.
