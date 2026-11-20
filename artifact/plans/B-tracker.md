# Tracker — vai B, round 3

Theo `PLAN-ROUND3.md` (vai B) và `HUONG-DAN-B.md`. Sắp theo hạn.

| ID | Việc | Đầu ra / khóa | Phụ thuộc | Hạn | Trạng thái | Ghi chú |
|---|---|---|---|---|---|---|
| B0 | Môi trường, `make apks`, 1 trial smoke | ghi chú môi trường | — | 19/11 | DONE 19/11 | smoke = rehearsal Test 6 trên P04Avd15 |
| B1 | Sàng AirGuard, Fedilab, CastBay | quyết định S1 | B0 | **21/11** | DONE 19/11: AirGuard build OK → đề xuất đi tiếp (b1-screening.md) | build / lời hứa / bọc đường gửi |
| B11 | Test 4: Android 14, 15 × pen, kill, reb, net | `life*` | B0 | 22/11 | DONE 19/11: 80+80 analysed, 2 replaced (card §6); keys `life*` in analysis, to summary.json with the next delivery | đêm 20 và 21/11; cần image android-34, android-35 arm64 |
| A10 | Chạy `triage/find_callers.py` trên acrafence + matomo APK | gửi A | `make apks`, `matomo/build.sh` | 22/11 | DONE 19/11 | `results/round3/a10/` |
| B3 | Tách lô trong `ChunkFence` + transport; 3 điều kiện × 20 | raw, `summary.json` | S0 | 24/11 | DONE 19/11 (v2): 120/120 valid; split recovers 20/20 prefirst, 0/20 prefix (card §6) | |
| B10 | Test 1: payload thật, EDGE/3G/LTE, rút ngẫu nhiên | `race*` | B0 | 25/11 | DONE 19/11 (protocol v3, guest netem): 180/180 valid; early 21/20/10 of 30, fence 0/30 (card §6) | |
| B4 | Chi phí transport + test 5 (chunk × sender) | `sweep*` | B0 | 26/11 | DONE 19/11: v1 + v2 (v2 = keys; 4 invalid, 2 cells < 20, card Outcome) | cắt đầu tiên |
| B12 | Test 2: build + chạy mutant; thêm tham số thư mục cho `matched_oracle.py` | `mut*` | A9 | 28/11 | DONE 19/11: base/M1/M2/M3 final, 38–40 valid each (card Outcome); M1 null → told A | |
| T6 | Test 6: Pixel 8a (Device Farm) + Galaxy M35 (RTL), TLS ×20 + lifecycle pen/kill/rev ×20 mỗi máy | `dev*` (chờ C chốt định nghĩa) | — | 28/11 | DATA DONE 19/11; Test 1 phần điện thoại (C11) không chạy — quyết định người dùng 20/11 | card `test6-card.md` §6; receiver: P USB, G relay RDB |
| B2 | App thật end-to-end (nếu S1 đi tiếp) | raw, `summary.json` | S1 | 28/11 | DONE 19/11 (AirGuard, protocol v1): 80/80 valid; stock 20/20 violating in pen/kill/reb, fenced 0/20; netloss deficit both; unknowns reported (card Outcome) | pen, kill, reb, net (+fstop) × 20 |
| B7 | Data freeze | commit raw, summary, PROTOCOL, EXCLUSIONS | tất cả | **29/11** | PREP 19/11: `results/round3/PROTOCOL.md`, `EXCLUSIONS.md` (make_exclusions.py); regenerate + final commit at freeze | không chạy thêm sau mốc |
| B8 | §6, appendix Artifact, sửa tài liệu cũ | văn bản | B7 | 2/12 | DRAFT 19/11: §6 one-line pointer + appendix "Round-3 Implementation and Harness" (body unchanged, 0 overfull/undefined); old docs fixed 19/11 (`review/artifact-revision-audit.md` is not in the repo); revisit after freeze | |
| B9 | Người ngoài clone + `make all` | log | B8 | 2/12 | SELF-CHECK 19/11 OK after Makefile fix (`results/round3/b9/`); still needs an outside person per plan | |
