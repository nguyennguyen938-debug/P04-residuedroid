# Thuật ngữ ranh giới (A1, chốt 18/11)

Paper chỉ dùng các chữ ở cột "Viết trong paper". Mỗi chữ ứng với đúng một sự kiện trong log, để oracle, bảng số và văn bản nói cùng một thứ. Ai viết §6, §7, appendix hay generator thì dùng bảng này.

## Phía gửi, theo thứ tự thời gian

| # | Viết trong paper | Nghĩa | Sự kiện trong log | Không viết |
|---|---|---|---|---|
| 1 | **authorization** (authorization log) | Bên gửi ghi ý định gửi một request. Chưa có byte nào ra socket | `AUTHORIZATION_LOGGED` (`HttpTransport`, `TlsTransport`) | "sent", "send event" |
| 2 | **TLS buffering** | Plaintext đã mã hóa thành record, nằm trong bộ đệm của app, chưa ghi ra socket | `TLS_BUFFERED` | "TLS sent" |
| 3 | **write attempt** | Một lần gọi ghi nonblocking, tối đa 4 KiB, ngay sau check | `WRITE_ATTEMPT`, `WRITE_RETURN_BOUNDARY` | "send attempt" |
| 4 | **handoff** (socket acceptance) | Socket nhận một prefix dương. Ghi nhận được 0 byte thì không phải handoff. Đây là ranh giới của Theorem 1 và 2 | `BYTES_ACCEPTED` với `n>0`; `REQUEST_HANDED_OFF` khi đã nhận hết request | "leaves the device", "handed to the network", "on the wire", "local acceptance" |
| 5 | **request receipt** (delivered) | Receiver nhận đủ một request. "delivered" chỉ dùng theo nghĩa này | Dòng request trong `receiver.jsonl` của sink | "remote receipt", "reaches the server" |
| 6 | **response receipt** | Bên gửi đọc được status của response | `RESPONSE_RECEIVED` | "completed" khi chưa nói rõ phía nào |
| 7 | **send failure** | Attempt kết thúc bằng lỗi. Prefix đã handoff trước lỗi vẫn tính là đã handoff | `SEND_FAILED` | "dropped" |
| 8 | **block** | Fence từ chối trước một write attempt | `BLOCK` | "filtered" |

## Phía policy

| Viết trong paper | Nghĩa | Sự kiện trong log |
|---|---|---|
| **withdrawal request** | Người dùng tắt, app bắt đầu giao dịch policy | `WITHDRAW_REQUEST` |
| **withdrawal commit** | Epoch mới và cờ grant đã ghi bền | `WITHDRAW_DURABLE` (ACRA, `Revision`), dòng `WITHDRAW` trong `eventTx` (fixture) |
| **acknowledgement** | App báo người dùng là đã rút. Luôn sau commit; withdrawal lỗi hay đang chờ thì không bao giờ được acknowledge | `WITHDRAW_ACK` |
| **re-grant** | Cấp lại đồng ý, epoch giữ nguyên | `REGRANT`, `REGRANTED`, `REGRANT_ACK` |

## Quy ước câu chữ

- "Prohibited submission" xét tại **handoff**, không xét tại authorization hay request receipt.
- Nói "after acknowledgement" khi mốc là lúc người dùng được báo; nói "after the withdrawal commits" khi mốc là trạng thái bền. Không dùng "after the withdrawal takes effect".
- Bằng chứng của stream-wrapper là **authorization-order**: chỉ biết thứ tự authorization so với withdrawal. Bằng chứng của channel transport là **accepted-byte**: biết prefix nào đã handoff. Không gộp hai loại vào cùng một con số.
- Byte đã handoff trước khi rút vẫn có thể tới receiver sau acknowledgement (Proposition "No recall"). Đó không phải vi phạm của fence.
