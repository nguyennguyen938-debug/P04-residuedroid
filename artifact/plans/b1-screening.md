# B1 — sàng app thật (S1, hạn 21/11)

Ba ứng viên theo plan (`PLAN-ROUND3.md` B1). Mỗi app kiểm 3 điều: build được từ source không; lời hứa nói gì về dữ liệu
đang chờ; đường gửi có bọc được bằng transport của ResidueDroid không. Mã nguồn lấy đúng commit F-Droid build (metadata
fdroiddata, 19/11), clone vào scratch của B (không commit). Lời hứa: `artifact/survey/promise_coding.csv` (C10).

| | AirGuard (`de.seemoo.at_tracking_detection`) | CastBay (`com.weenas.castbay`) | Fedilab (`fr.gouv.etalab.mastodon`) |
|---|---|---|---|
| Phiên bản / commit F-Droid | 3.1.3, `d515c534` | 1.10.1, `f06360a7` | 3.45.1, `1dfcb7f3` |
| Build từ source | F-Droid build từ source (Apache-2.0); Kotlin/Hilt, không NDK. **Chưa build thử trên Mac** (hoãn tới khi B11 xong: RAM) | F-Droid build từ source (GPL-3.0) nhưng **cần NDK + submodule native** (UxPlay, OpenSSL, alac, libplist) → build nặng, rủi ro | F-Droid build (GPL-3.0) |
| Lời hứa (C10) | PENDING: "Support the project by sharing some anonymous data" (tham gia nghiên cứu) | PENDING: "Send Anonymous Usage Statistics" | COLLECT_ONLY (C sửa mã): "Enable crash reports", gửi qua email |
| Dữ liệu đang chờ | Bản ghi thiết bị/beacon trong DB Room, gửi theo lô từ `lastDataDonation` | Bộ đếm theo ngày trong SharedPreferences, gửi các ngày đã xong | Báo cáo crash ACRA |
| Đường gửi | `SendStatisticsWorker` (WorkManager periodic, retry/backoff theo giờ) → Retrofit/OkHttp `POST donate_data` | `UsageStats.sendFinishedDays` (thread, gọi từ `AirPlayService` và `WakeJobService`) → `HttpURLConnection` POST `/api/stats` | ACRA `MailSender` → intent email (rời app qua app mail) |
| Rút đồng ý | `removeShareData()` = `cancelUniqueWork`; **worker không tự kiểm tra lại cờ `share_data` trong `doWork`** → lần gửi đang chạy / đã lấy dữ liệu vẫn đi tiếp | `setOn(false)` xoá prefs (xoá cả dữ liệu đang chờ) rồi gửi yêu cầu xoá phía server; chỉ còn cửa sổ race khi đang gửi | không có đường mạng của app để chặn |
| Bọc được không | Được: thay lời gọi `donateData` bằng gửi qua transport có fence (hoặc OkHttp custom body ghi qua fence); job bền là WorkManager | Được, dễ: thay `post()` bằng `HttpTransport` của ResidueDroid | Không phù hợp (gửi qua email, ngoài mediated path) |
| Lưu ý thí nghiệm | Bản debug `doWork` trả về ngay (không gửi) → cần build release-like hoặc patch cờ; trỏ base URL về sink thí nghiệm (NonFreeNet) | Dữ liệu chờ bị xoá ngay khi rút → residue chỉ ở cửa sổ đang gửi | — |

## Đề xuất cho S1 (B, 19/11)
- **Đi tiếp với AirGuard** làm app thật chính: job bền (WorkManager) + dữ liệu chờ trong DB + đường gửi mạng bọc được +
  lời hứa PENDING, và worker không kiểm tra lại đồng ý — đúng loại residue bài nghiên cứu.
- **CastBay dự phòng** (đường gửi đơn giản) nếu AirGuard không build được; build native nặng.
- **Bỏ Fedilab** cho B2 (gửi qua email, không có đường mạng để fence; C đã mã COLLECT_ONLY).
- Bước còn lại trước S1: build thử AirGuard trên Mac (sau B11, ~tối 19/11 hoặc 20/11) và ghi kết quả vào đây.
