# Plan P04 ResidueDroid: 3 vai chạy song song (bản 2, 18/11)

**Mốc cứng:** đăng ký abstract **thứ Sáu 27/11**, nộp bài **thứ Sáu 4/12** (AoE). Data freeze **29/11**.

**Khác bản 1:**
- Thêm 6 test để tăng điểm. Test 1 đến 3 là bắt buộc; test 4 đến 6 có thể cắt nếu trễ.
- Bớt việc cho B, vì B là chỗ nghẽn (một người, một máy Mac chạy emulator):
  - Phân loại mediation (B5 cũ) chuyển sang A.
  - Test 2: A thiết kế và viết code, B chỉ chạy.
  - Test 3 giao cho C.
  - Test 6 có hai đường, chốt ở S0: chạy trên cloud thì C làm; mua máy thì B làm.
- Thêm hàng đợi emulator, để B biết ngày nào chạy gì.
- Thêm ngân sách cho máy thật.

## Sáu test bổ sung

| # | Test | Trả lời | Ai | Chỗ trong bài | Mức |
|---|---|---|---|---|---|
| 1 | Race tự nhiên khi gửi dữ liệu lớn qua mạng chậm | R1 | B (B10) | §7, thân bài | Bắt buộc |
| 2 | Đột biến nhãn, kèm bộ kiểm nhãn lúc test | R2 | A thiết kế và viết code (A9), B chạy (B12) | §7, thân bài | Bắt buộc |
| 3 | Thống kê lời hứa thật trong các app ứng viên | R3 | C (C10), lane C gán nhãn | §3 | Bắt buộc |
| 4 | Lifecycle trên Android 14 và 15 | R1, R3 | B (B11) | §7 một đoạn, bảng ở appendix | Cắt được |
| 5 | Quét kích thước chunk và số sender | R1 | B (gộp vào B4) | Appendix, §7 một câu | Cắt đầu tiên |
| 6 | Điện thoại thật | R1, R3 | C (C11) qua AWS, hoặc B (B6) qua máy mua | §7a, §7 một đoạn | Cắt được phần lifecycle |

**Thứ tự cắt khi trễ:**
1. Bỏ test 5.
2. Bỏ phần lifecycle của test 6.
3. Thu test 4 lại còn một bản Android.

Test 1 đến 3 phải giữ. Test nào không kịp data freeze thì bỏ khỏi thân bài, không chạy đuổi.

## Năm nguyên tắc để ít phải chờ nhau

1. **Chốt giao diện ngay buổi đầu.** Số liệu giữa B và C đi qua file `summary.json`, có schema và tên macro định sẵn, gồm cả khóa cho 6 test mới. C viết văn bản bằng macro trước khi có dữ liệu. Khóa nào còn thiếu sẽ hiện `??`, và bước kiểm cuối chặn mọi bản còn `??`. Không ai gõ số tay.
2. **Mỗi vai sở hữu file riêng.** Mỗi vai làm trên nhánh riêng (`a-theory`, `b-exp`, `c-results`) và merge vào `main` mỗi ngày.
3. **Mỗi vai có sẵn việc không phụ thuộc ai** cho tuần đầu.
4. **Mỗi vai tự giữ số trang của mình.** Thân bài hiện dài đúng 12 trang. Ai thêm nội dung thì tự cắt bù trong phần mình, phần dư chuyển xuống appendix.
5. **B giữ hàng đợi emulator.** Ai cần chạy trên emulator, ví dụ mutant của A, thì giao script cho B để B xếp vào hàng đợi. Không ai khác tự chạy emulator trên máy Mac của B.

## Sở hữu file

| Vai | File |
|---|---|
| A | `02-background`, `04-design`, `05-theory`, `09-related-work`, phần đầu intro (bối cảnh, approach, contributions), appendix "Uncovered Paths", `fig2-design`, `references.bib` (người khác chỉ thêm vào cuối file), **thư mục mới `artifact/mutation/**`** |
| B | Toàn bộ `artifact/**`, trừ các script render, `artifact/mutation/**` và `artifact/devicefarm/**`; cùng `06-implementation` và appendix "Artifact" |
| C | `00-abstract`, file mới `01b-evidence`, `03-measurement`, `07-evaluation`, `07a-setup`, `08-discussion`, `10-conclusion`, `generated/*`, các script `render*.py`, `main.tex`, **thư mục mới `artifact/devicefarm/**`**. Thư mục lô cho lane C nằm ngoài repo |

## Vai A: lý thuyết

| ID | Việc | Đầu ra | Phụ thuộc | Hạn |
|---|---|---|---|---|
| A1 | Bảng thuật ngữ về ranh giới: authorization, write attempt, socket acceptance, receiver completion, response receipt, acknowledgement. Rà §1 đến §5 để dùng thống nhất | Bảng gửi B và C | Không | 19/11 |
| A2 | Máy trạng thái vòng đời: dữ liệu lưu → job xếp hàng → bản ghi TLS đã đệm → prefix socket đã nhận → receiver nhận đủ → response. Mỗi bước chuyển ghi rõ chỗ check policy, kết quả khi crash, quy ước retry, và ánh xạ vào tên sự kiện trong `HttpTransport` và `TlsTransport` | Bảng hoặc hình ở §5 | Không | 23/11 |
| A3 | Hình thức hóa chính sách tách lô đã chốt ở S0 | Đoạn §4 và §5 | S0 | 24/11 |
| A4 | Nghĩa vụ của nhà phát triển về nhãn: checklist khi thêm nguồn dữ liệu, bản tóm tắt, hàng đợi hay transport, cùng cách dùng bộ kiểm nhãn của A9. Câu chữ xác nhận rút cho người dùng | §4 và appendix | A9 | 26/11 |
| A5 | Viết lại novelty cho sát | Contributions và §9 | Không | 28/11 |
| A6 | Gửi C ba câu claim cho abstract đăng ký | 3 câu | Không | 26/11 |
| A7 | Cắt trang trong phần của mình, bỏ en dash | Đúng ngân sách trang | Không | 1/12 |
| A8 | Đọc chéo §7 của C: có claim nào vượt phạm vi định lý không | Ghi chú gửi C | C7 | 2/12 |
| **A9** | **Test 2.** Mỗi mutant xóa một chỗ truyền nhãn: nhãn ở nơi thu thập, phép hợp nhãn khi tạo dữ liệu dẫn xuất, nhãn trong job extras, bước so epoch. Viết bộ kiểm nhãn lúc test dựa trên tracer: mỗi item gửi đi phải mang tập nhãn bao trùm mọi nguồn mà tracer tìm thấy trong nội dung. Code để trong `artifact/mutation/`, chạy được trên fixture trước, trên app thật sau | Mutant, script kiểm, hướng dẫn chạy giao B | Không (phần app thật cần B2) | 24/11 |
| **A10** | **Chuyển từ B5 cũ.** Phân loại các site mà mediation checker gắn cờ (5 site ACRA, 4 site Matomo, các site của app thật) vào reachable, đã bọc, hoặc ngoài cấu hình | CSV triage, đưa vào appendix Uncovered Paths | Site của app thật cần S1 | 27/11 |

## Vai B: thí nghiệm

| ID | Việc | Đầu ra | Phụ thuộc | Hạn |
|---|---|---|---|---|
| B0 | Chọn máy chạy (khuyên Mac Apple Silicon, ảnh arm64 như paper). Dựng JDK 17, SDK, emulator; chạy `make apks` và 1 trial smoke | Ghi chú môi trường | Không | 19/11 |
| B1 | Sàng app thật trong 18 ứng viên: AirGuard (`de.seemoo.at_tracking_detection`), Fedilab (`fr.gouv.etalab.mastodon`), CastBay (`com.weenas.castbay`). Mỗi app kiểm 3 điều: build được từ source không, lời hứa nói gì về dữ liệu đang chờ, đường gửi có bọc được không | Quyết định ở S1 | B0 | 21/11 |
| B2 | Tích hợp app thật từ đầu đến cuối, chạy pen, kill, reb, net (thêm fstop nếu kịp), mỗi lịch 20 trial; so bản gốc với bản có fence, kèm luồng được phép làm đối chứng | raw và `summary.json` | S1 | 28/11 |
| B3 | Tách lô theo chính sách S0, chạy 3 điều kiện × 20 trial. Đo tỷ lệ giữ được thư hợp lệ và số lần gửi lại thành công | raw và `summary.json` | S0 | 24/11 |
| B4 | Chi phí transport với thứ tự ngẫu nhiên và tải đồng thời, **gộp test 5**: chunk 1, 4, 16, 64 KiB × 1, 2, 4, 8, 16 sender. Thiếu giờ máy thì thu lưới lại | raw và `summary.json` | B0 | 26/11 |
| ~~B5~~ | Chuyển sang A10 | | | |
| B6 | **Test 6, đường 1** (nếu S0 chọn mua máy): cắm điện thoại vào Mac, chạy test 1 rút gọn, TLS barrier, backpressure, và lịch pen, kill, reb, net | raw và `summary.json` | Máy về, B0 | 28/11 |
| B7 | **Data freeze:** commit raw, summary, PROTOCOL và EXCLUSIONS. Sau mốc này không chạy thêm | Commit | Không | **29/11** |
| B8 | Viết §6 và appendix Artifact. Cập nhật `INTEGRATION.md`, `artifact-revision-audit.md`, `README`, `STATUS`, `PLAN` | Văn bản | B7 | 2/12 |
| B9 | Nhờ một người chưa từng đụng vào dự án clone repo và chạy `make all` | Log | B8 | 2/12 |
| **B10** | **Test 1.** Payload theo kích thước thật (báo cáo ACRA vài trăm KB, lô analytics, backup vài MB). Giới hạn mạng emulator ở mức EDGE, 3G, LTE. Thời điểm rút chọn ngẫu nhiên đều trong suốt quá trình upload, không dùng barrier. So layered early với fence: tỷ lệ trial có byte được nhận sau ack, đối chiếu với Eq. 2 | raw và `summary.json` | B0 | 25/11 |
| **B11** | **Test 4.** Dựng AVD Android 14 và 15 arm64, chạy pen, kill, reb, net với một baseline yếu, layered early và ResidueDroid. Không cần viết code mới | raw và `summary.json` | B0 | 22/11 |
| **B12** | **Test 2.** Chạy các mutant của A9 trên fixture. Nếu B2 xong trước 27/11 thì chạy thêm trên app thật | raw và `summary.json` | A9 | 28/11 |

### Hàng đợi emulator của B

Đây là mục tiêu, B được đổi thứ tự. Việc chạy dài thì chạy qua đêm.

| Ngày | B làm ban ngày | Emulator chạy |
|---|---|---|
| 19/11 | B0 | Smoke |
| 20/11 | B1 | B11 trên Android 14 |
| 21/11 | B1, báo S1 | B11 trên Android 15 |
| 22/11 | Code B10 | B4 cùng test 5 |
| 23/11 | Code B3, bắt đầu B2 | B10 |
| 24/11 | B2 | B3 |
| 25/11 | B2 | B12 trên fixture, chạy lại B10 nếu cần |
| 26/11 đến 27/11 | B2 | B2 |
| 28/11 | Kiểm số | B12 trên app thật, chạy bù |
| 29/11 | B7 data freeze | |

## Vai C: số liệu và kết luận

| ID | Việc | Đầu ra | Phụ thuộc | Hạn |
|---|---|---|---|---|
| C0 | Clone sạch từ GitHub, chạy `make all`. Tách intro thành hai file | Log, file `01b-evidence` | Không | 19/11 |
| C1 | Dọn phần sinh số: sửa generator đang in "stock sent", "acra delivered" ở đầu câu; đưa số kiểm định ở §3 vào macro; bỏ macro `valShallow*`; bỏ en dash | Bản build sạch | Không | 20/11 |
| C2 | Hạch toán phần thiếu hụt luồng được phép của matched campaign lớn (168, 96 và 60 trên 14.000) theo các nguyên nhân loại trừ nhau | Bảng và đoạn văn | Không | 24/11 |
| C3 | Kết quả ở mức trial: số paired trial có vi phạm hoặc unknown, theo lịch và AVD; độ nhạy khi coi unknown là vi phạm; cận trên khi không có sự kiện nào | Bảng và đoạn văn | Không | 24/11 |
| C4 | Bảng ma trận triển khai: build × transport × hợp đồng × retry × ranh giới bằng chứng × loại trừ | Bảng | Không | 26/11 |
| C5 | Khung §7 bằng macro, cho các thí nghiệm mới và test 1, 2, 4, 5, 6; khung §3 cho test 3; renderer đọc `summary.json`. Chuẩn bị 2 khung: có app thật và phương án dự phòng | Văn bản và script | S0, S1 | 27/11 |
| C6 | Viết abstract đăng ký. Tác giả tự bấm đăng ký sớm hơn hạn một ngày | Abstract | A6 | **26/11** |
| C7 | Đổ số thật vào §3, §7, rồi cập nhật abstract, đoạn Evidence, §8 (external validity theo máy B và máy thật) và §10 | Văn bản | B7 | 2/12 |
| C8 | Text freeze, cắt tổng số trang. QA PDF: 10pt, ≤55 dòng mỗi cột, thân ≤12 trang, 0 overfull, 0 `??`, có ghi chú dùng LLM | PDF | Mọi việc khác | 3/12 |
| C9 | Nộp bài | | | **4/12** |
| **C10** | **Test 3.** Gom văn bản công khai của 18 app ứng viên (mô tả trên F-Droid, chuỗi trong màn setting lấy từ source, privacy policy) vào thư mục lô ngoài repo. Lane C (tài khoản Claude phụ, không phải vai C) xếp mỗi app vào 4 loại hợp đồng. C tự kiểm mọi mục bị gắn cờ. Còn thời gian thì mở rộng lên 65 app. Số liệu chỉ viết là của mẫu đã khảo sát | Bảng cho §3 | Không | 25/11 |
| **C11** | **Test 6, đường 2** (nếu S0 chọn AWS). Ngày 20 và 21/11 chạy thử 1 lượt để biết test spec làm được gì: adb, network profile, reboot, cắt mạng. Sau đó chạy TLS barrier, backpressure, test 1 rút gọn và lifecycle không cần reboot trên 2 máy khác hãng (Pixel và Samsung). Receiver đặt trên một máy EC2 cùng vùng us-west-2 | raw và `summary.json` | C0 | 28/11 |

## Lịch và 4 điểm đồng bộ

| Ngày | Mốc | Ai |
|---|---|---|
| 18/11 đến sáng 19/11 | **S0**, họp 1 đến 2 giờ: chốt sở hữu file, schema `summary.json` (cả 6 test), tên macro, ngân sách trang, chính sách tách lô. **Chọn đường cho test 6:** mua máy hay thuê AWS, ai trả tiền. Tạo tài khoản AWS và nhập thẻ thì người dùng tự làm | Cả ba |
| 21/11 | **S1**: B báo đi tiếp hay bỏ app thật. C báo lượt chạy thử Device Farm làm được gì | B, C |
| 26/11 | **S2**: chốt abstract đăng ký | A, C |
| 29/11 | **S3**: data freeze | B, C → C |
| 2/12 | **S4**: text freeze, cắt trang | Cả ba |

Những chỗ một vai phải chờ vai khác, và việc làm trong lúc chờ:
- **A1 → B, C:** B và C cứ dùng thuật ngữ hiện có của paper.
- **A6 → C6:** C viết nháp abstract trước rồi ghép claim vào sau.
- **A9 → B12:** B chạy B10 và B3 trước.
- **B7 → C7:** C đã có khung viết bằng macro, chỉ cần đổ số.

## Quyết định đã chốt (18/11)

| Việc | Quyết định | Ai làm tiếp |
|---|---|---|
| Test 6 | **Thuê AWS Device Farm** (đường 2), không mua máy. Bộ chuẩn bị ở `artifact/devicefarm/` | B (Duy) lo hết: tạo tài khoản AWS, áp `real-device.patch`, build app TLS, chạy thử 1 máy rồi 2 máy khác hãng. Xem `HUONG-DAN-B.md` |
| Chính sách tách lô | Fence chặn trước khi có byte nào ra socket thì chia item theo nhãn: item bị cấm bị loại hẳn, item hợp lệ thành request mới và qua fence lại; tối đa 1 lần tách mỗi attempt; đã có byte được nhận thì không tách | A3 đã viết xong trong §5; B cài vào fence và chạy B3 (3 điều kiện × 20 trial) |

## Ngân sách máy thật (test 6)

| Cách | Giá | Chạy được | Ghi chú |
|---|---|---|---|
| Mua Pixel 7 cũ (hàng xách tay) | Khoảng 5 đến 9 triệu đồng | Tất cả, kể cả reb, net và root | Dùng lại được. Giá niêm yết trên trang bán lẻ, phải hỏi lại |
| AWS Device Farm, trả theo phút | 0,17 USD mỗi phút máy. Có thể có 1.000 phút dùng thử một lần, phải kiểm lại | Transport, lifecycle không cần reboot | Ước khoảng 1.100 phút cho 2 máy, gần 190 USD |
| AWS Device Farm, gói không giới hạn | 250 USD mỗi slot mỗi tháng | Như trên | Chỉ có lợi khi dùng trên khoảng 1.470 phút mỗi slot |
| Firebase Test Lab | 5 USD mỗi giờ máy thật; gói Blaze có 30 phút miễn phí mỗi ngày | Chỉ test viết dạng instrumentation, không có adb từ bên ngoài | Rẻ nhất nhưng phải viết lại harness |
| BrowserStack App Automate | 199 đến 249 USD mỗi tháng cho 1 phiên song song | Chưa rõ có adb shell không | Không khuyên |

**Ước lượng số phút trên Device Farm** (giả định mỗi trial 2 đến 3 phút, đo lại sau lượt chạy thử):
- Chạy thử và sửa test spec: 150 phút.
- Mỗi máy: TLS barrier và backpressure 120 phút; test 1 rút gọn 120 phút; lifecycle không reboot 120 phút. Tổng 360 phút mỗi máy, 720 phút cho 2 máy.
- Dự phòng 30%: khoảng 260 phút.
- **Tổng khoảng 1.100 phút, gần 190 USD (khoảng 5 triệu đồng).** Máy EC2 làm receiver dưới 10 USD cho cả đợt.

**Khuyên:** nếu nhận được máy trước 22/11 thì mua. Tốn ngang thuê AWS mà chạy được đủ lịch, và B dùng harness có sẵn. Chỉ thuê AWS khi không mua được, hoặc khi muốn thêm máy hãng thứ hai.

## Rủi ro và phương án dự phòng

- **App thật không build được hoặc không tích hợp kịp:** tại S1 chuyển sang phương án dự phòng (giữ ACRA và Matomo, nói rõ giới hạn). Test 2 vẫn chạy trên fixture.
- **Device Farm không cho reboot hay cắt mạng:** giữ reb và net ở emulator, ghi rõ trong §7a.
- **Lượt chạy trên Device Farm bị giới hạn thời gian** (một nguồn ngoài nói tối đa 150 phút): chia thành nhiều lô nhỏ.
- **Máy thật cắm sạc nên không tự vào Doze:** ép bằng `dumpsys battery unplug` và `dumpsys deviceidle force-idle`, ghi rõ trong §7a.
- **B chạy trên x86_64 thay vì arm64:** không gộp số thời gian với các campaign cũ.
- **Thân bài vượt 12 trang:** chuyển kết quả stream-wrapper cũ (đầu §7) xuống appendix và rút gọn §3. Test 4, 5, 6 chỉ giữ một đoạn trong thân bài.
- **Không plan nào đảm bảo được nhận.** Nếu test 1 đến 3 ra kết quả tốt và app thật chạy được, bài có thể lên mức borderline hoặc weak accept.

## Nguồn giá (tra ngày 18/11/2026)

- AWS Device Farm: https://aws.amazon.com/device-farm/pricing
- Firebase Test Lab: https://firebase.google.com/docs/test-lab/usage-quotas-pricing
- BrowserStack (nguồn thứ ba): https://www.g2.com/products/browserstack/pricing
- Pixel 7 cũ: https://www.viettablet.com/dien-thoai/dien-thoai-google/pixel-7-7-pro, https://www.xtmobile.vn/google-pixel-7-cu-99
- Adb trong custom test environment của Device Farm: https://docs.aws.amazon.com/devicefarm/latest/developerguide/custom-test-environments.html
