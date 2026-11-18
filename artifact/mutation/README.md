# Bộ đột biến nhãn (test 2, A9)

Câu hỏi của Reviewer 2: maintainer làm sao biết nhãn đã truyền đủ? Bộ này trả lời bằng số. Mỗi mutant xóa hoặc làm sai một chỗ truyền nhãn trong fixture, rồi đo hai thứ:

1. Lúc chạy thật, oracle có bắt được vi phạm không. Nhãn hợp lệ nhưng thiếu nguồn thì fence không biết, nên dữ liệu lọt.
2. Lúc test, `label_check.py` có bắt được nhãn sai không. Bộ kiểm so nhãn mà fence đã kiểm với nguồn mà tracer tìm thấy trong nội dung.

Câu cần ra trong §7 có dạng: "với mutant X, dữ liệu lọt trong a/20 trial lúc chạy; bộ kiểm lúc test gắn cờ b/b item sai nhãn".

## Các patch

Mọi patch áp vào source gốc của `artifact/fixture`, chỉ dùng cho bản build thử đột biến, không bao giờ commit vào `fixture/src`.

| Patch | Chỗ sửa | Lúc chạy, dự kiến | Bộ kiểm, dự kiến |
|---|---|---|---|
| `I0-labels-in-body` | `Fence.body`: thêm trường `labels` vào mỗi item gửi đi | Không đổi hành vi. Bắt buộc áp cho mọi bản build của đợt này, kể cả bản gốc | Bản gốc: mọi item `ok` |
| `M1-union-latest` | `Work.aggregate`: nhãn của bản tóm tắt chỉ giữ nhãn mới nhất thay vì hợp mọi nguồn | T5: bản tóm tắt gộp bản ghi e0 và e1 được dán nhãn e1, nên lọt sau khi cấp lại đồng ý (nếu lúc gộp có cả hai epoch) | Item tóm tắt `incomplete`, thiếu `analytics:0` |
| `M2-stale-epoch` | `Work.run`: bản ghi thô dán epoch hiện tại thay vì epoch lúc thu thập | T5: bản ghi e0 lọt sau khi cấp lại đồng ý | Item thô e0 `incomplete` |
| `M3-extras-drop` | `Work.summaryExtras`: không chép nhãn vào job extras | Nhãn rỗng nên fence chặn (fail closed): mất thư hợp lệ, không lọt | Item tóm tắt không tới receiver; xem số thiếu thư hợp lệ |

M3 là mutant đối chứng: nó cho thấy thiếu nhãn hẳn thì an toàn nhưng mất dữ liệu hợp lệ, còn nhãn hợp lệ nhưng thiếu (M1, M2) mới là chỗ nguy hiểm.

## Build (vai B)

Trên máy có Android SDK, từ gốc repo:

```bash
for m in base M1-union-latest M2-stale-epoch M3-extras-drop; do
  git apply artifact/mutation/patches/I0-labels-in-body.patch
  [ "$m" = base ] || git apply "artifact/mutation/patches/$m.patch"
  (cd artifact/fixture && VARIANTS=mfence OUTDIR="build/apk_mut_$m" ./build.sh)
  git checkout -- artifact/fixture/src
done
```

Mỗi bản build vẫn có package `org.residuelab.mfence`, nên chạy từng mutant một trên cùng AVD.

## Chạy (vai B)

```bash
cd artifact
python followup/campaign.py --serial emulator-5600 --avd P04AvdA --port 8795 --variants mfence \
  --schedules pending,reboot --trials 20 --apkdir "fixture/build/apk_mut_$m" --out "results/mutation/$m"
```

Lịch `pending` và `reboot` đã đủ, vì T5 rút rồi cấp lại đồng ý trong mọi lịch. Hai mươi trial mỗi lịch, mỗi mutant.

## Phân tích

```bash
python mutation/label_check.py --name "$m" --out "results/mutation/$m/labels.json" "results/mutation/$m"
```

Số vi phạm lúc chạy lấy từ oracle đang dùng cho matched campaign (`followup/matched_oracle.py`). Script đó đang ghi cứng danh sách instance, nên B cần thêm tham số đường dẫn thư mục chạy trước khi dùng cho `results/mutation/*`.

## Đã kiểm ở đây

- Bốn patch đều áp sạch vào source gốc, cả riêng lẻ lẫn I0 kèm từng mutant (`git apply --check`).
- `label_check.py` qua self-check, và đọc đúng định dạng receiver của matched campaign. Trên dữ liệu cũ (chưa có I0) mọi item ra `missing`, đúng như dự kiến.
- **Chưa build và chưa chạy** trên Android: máy làm bước này không có Android SDK.
