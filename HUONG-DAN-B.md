# Hướng dẫn cho vai B (thí nghiệm), round 3

Plan đầy đủ nằm ở `PLAN-ROUND3.md`. File này chỉ gom những gì B cần để bắt tay vào làm. Hạn cứng: **data freeze 29/11**, nộp bài 4/12.

## Bắt đầu

Phần việc của A và C nằm trên nhánh `ac-round3` (đã có sửa Makefile và các renderer). Làm từ nhánh đó, trên nhánh riêng:

```bash
git fetch origin
git checkout -b b-exp origin/ac-round3
```

B sở hữu `artifact/**`, trừ: các script render (`scripts/render*.py`, `revision/render_revision.py`, `followup/render.py`) và các thư mục mới `mutation/`, `triage/`, `survey/`, `devicefarm/`. Các file đó có thể đọc, nhưng nếu cần sửa thì báo C.

## Đã chốt ở S0 (18/11)

- **Test 6 chạy trên AWS Device Farm.** B tạo tài khoản AWS, bật thanh toán, kiểm còn 1.000 phút dùng thử không.
- **Chính sách tách lô.** Nếu fence chặn trước khi có byte nào ra socket thì chia item theo nhãn: item bị cấm bị loại hẳn, item hợp lệ thành request mới và qua fence lại. Mỗi attempt tách tối đa 1 lần. Đã có byte được nhận thì không tách. Lý thuyết đã viết ở §5, đoạn "Splitting blocked requests".

## Cách giao số cho C

Ghi đúng một file `artifact/results/round3/summary.json` dạng `{tên: giá trị}` phẳng. Tên lấy đúng theo `SCHEMA` trong `artifact/scripts/render_tests.py`. C chạy renderer, khóa nào thiếu sẽ hiện `??` trong PDF. Không gõ số tay vào `.tex`.

| Test | Khóa trong `summary.json` |
|---|---|
| 1, race tự nhiên | `raceTrials`, `raceEdgeLayer`, `raceEdgeFence`, `raceThreegLayer`, `raceThreegFence`, `raceLteLayer`, `raceLteFence`, `racePredPct`, `raceObsPct` |
| 2, đột biến nhãn | `mutTrials`, `mutOneLeak`, `mutOneFlagged`, `mutOneWrong`, `mutTwoLeak`, `mutTwoFlagged`, `mutTwoWrong`, `mutThreeDeficit` |
| 4, Android 14 và 15 | `lifeFourteenTrials`, `lifeFourteenLayer`, `lifeFourteenFence`, `lifeFifteenTrials`, `lifeFifteenLayer`, `lifeFifteenFence` |
| 5, quét chunk và sender | `sweepAckSmallMs`, `sweepAckLargeMs`, `sweepCpuSmall`, `sweepCpuLarge` |
| 6, máy thật | `devModel`, `devAndroid`, `devTrials`, `devEarlyComplete`, `devFenceAfterAck` |

Test 3 (lời hứa) C đã làm xong, không cần khóa nào từ B.

## Việc, theo thứ tự hạn

| ID | Việc | Hướng dẫn | Hạn |
|---|---|---|---|
| B0 | Dựng môi trường trên Mac, `make apks`, 1 trial smoke | Plan | 19/11 |
| B1 | Sàng app thật (AirGuard, Fedilab, CastBay), báo đi tiếp hay bỏ | Plan | **21/11 (S1)** |
| B11 | Test 4: AVD Android 14 và 15, lịch pen, kill, reb, net; không cần code mới, chạy qua đêm 20 và 21/11 | Plan | 22/11 |
| A10 phần còn lại | Chạy `python artifact/triage/find_callers.py artifact/acra/build/apk/acrafence.apk artifact/matomo/build/matomo.apk`, gửi kết quả cho A | `artifact/triage/` | 22/11 |
| B3 | Cài chính sách tách lô vào `ChunkFence` và transport; 3 điều kiện × 20 trial; đo tỷ lệ item hợp lệ giữ được | §5 và plan | 24/11 |
| B10 | Test 1: payload thật, mạng EDGE, 3G, LTE, thời điểm rút ngẫu nhiên, layered early so với fence | Plan | 25/11 |
| B4 | Chi phí transport gộp test 5 (chunk 1, 4, 16, 64 KiB × 1, 2, 4, 8, 16 sender) | Plan | 26/11 |
| B12 | Test 2: build và chạy bộ đột biến; thêm tham số thư mục chạy cho `followup/matched_oracle.py` | `artifact/mutation/README.md` | 28/11 |
| Test 6 | Áp `real-device.patch`, build app TLS, chạy thử 1 máy rồi 2 máy khác hãng trên Device Farm | `artifact/devicefarm/README.md` | 28/11 |
| B2 | App thật từ đầu đến cuối (nếu S1 đi tiếp) | Plan | 28/11 |
| B7 | **Data freeze:** commit raw, `summary.json`, PROTOCOL, EXCLUSIONS | | **29/11** |
| B8 | §6, appendix Artifact; sửa tài liệu cũ: `INTEGRATION.md` và `artifact-revision-audit.md` còn ghi "không có HTTPS", `STATUS.md` ghi 17 trang, `PLAN.md` ghi "review anonymous" | | 2/12 |
| B9 | Nhờ một người chưa đụng dự án clone repo và chạy `make all` | | 2/12 |

Test nào không kịp 29/11 thì bỏ khỏi thân bài, không chạy đuổi. Thứ tự cắt khi trễ: test 5, rồi phần lifecycle của test 6, rồi thu test 4 còn một bản Android.

## A và C đã sửa gì trong vùng của B

- `artifact/Makefile`: thêm `followup/deficit_causes.py` và `scripts/render_tests.py` vào pipeline.
- File mới `artifact/followup/deficit_causes.py`, kết quả ở `results/review-followup-20261115/permitted-deficit-causes.json`.
- `scripts/render.py` đọc và ghi UTF-8, và không cần file index F-Droid 72 MB nữa (dùng `static/data/index/eligible.json`).

## Hai điều cần biết khi chạy

- Toàn bộ 448 thư hợp lệ bị thiếu trong matched campaign đều đến từ lịch reboot, vì `UpJob.onStopJob` trả `false` nên job bị dừng lúc tắt máy không được xếp lại. Không phải do chỗ đặt check. Nếu đổi hành vi này cho các lượt chạy mới thì ghi vào PROTOCOL, vì số thiếu hụt sẽ không so được với campaign cũ.
- Mọi lượt chạy trên Device Farm phải ghi chế độ receiver (qua USB hay qua mạng thật) để C viết đúng trong §7a.
