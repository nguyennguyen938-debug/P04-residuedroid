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
| B4 | Chi phí transport + test 5 (chunk × sender) | `sweep*` | B0 | 26/11 | DONE 20/11: v3 = keys (receiver timeout 300 s; 1 invalid, 2 replacement blocks, every cell 20); v1, v2 reported (card) | cắt đầu tiên |
| B12 | Test 2: build + chạy mutant; thêm tham số thư mục cho `matched_oracle.py` | `mut*` | A9 | 28/11 | DONE 20/11 v2 (regrant_agg, A approved): M1 24/40 leaking, M2 39/39, M3 0/40; keys from v2; v1 reported (card) | |
| T6 | Test 6: Pixel 8a (Device Farm) + Galaxy M35 (RTL), TLS ×20 + lifecycle pen/kill/rev ×20 mỗi máy | `dev*` (chờ C chốt định nghĩa) | — | 28/11 | DONE 21/11: data 19/11; keys `dev*` (C1) + `devLife*` computed 21/11 (pending SCHEMA, C); Test 1 on a phone (C11) DONE 21/11, keys `racePhone*` (pending SCHEMA) | card `test6-card.md` §6; receiver: P USB, G relay RDB |
| B2 | App thật end-to-end (nếu S1 đi tiếp) | raw, `summary.json` | S1 | 28/11 | DONE 19/11 (AirGuard, protocol v1): 80/80 valid; stock 20/20 violating in pen/kill/reb, fenced 0/20; netloss deficit both; unknowns reported (card Outcome) | pen, kill, reb, net (+fstop) × 20 |
| B7 | Data freeze | commit raw, summary, PROTOCOL, EXCLUSIONS | tất cả | **29/11** | RE-DECLARED 22/11 after group 2 (G2a, G2b; reopened 21/11 by leader decision); first declared 21/11: data freeze declared (all runs done: B12 v2, Test 1 phone); later changes only to summary.json keys computed by script from frozen data (C1/C3) | không chạy thêm sau mốc |
| B8 | §6, appendix Artifact, sửa tài liệu cũ | văn bản | B7 | 2/12 | DONE 21/11: C reviewed §6 + appendix in PR #2 (C6: OK; C changes "serialises" to "serializes") | |
| G2a | Group 2 (PR #4, leader 21/11): early check + socket close on withdrawal, B10 v3 race, modes early/close/fence × 30 per profile | analysis JSON (no SCHEMA keys yet) | — | 29/11 | DONE 22/11: 270/270 valid; violations early 20/21/9 of 30, close 0/30, fence 0/30 per profile; close aborts 18 delivered requests (exploratory) and adds a few ms to the ack | card `g2close-card.md` §6 |
| G2b | Group 2: AirGuard layered-early build, B2 schedules × 20, three builds per trial | analysis JSON (no SCHEMA keys yet) | G2a (one emulator at a time) | 29/11 | DONE 22/11: 80/80 valid; stock 20/20, fenced 0/20, layered 0/20 in pending/kill/reboot; netloss 0 for all (deficit 80 each) | card `g2layer-card.md` §6 |
| B9 | Người ngoài clone + `make all` | log | B8 | 2/12 | SELF-CHECK 19/11 OK; OPEN: an outside person runs clone + `make -C artifact all` (user finds the person) by 2/12 | |


**Handoff 21/11:** all B runs done, data frozen 21/11, final report `plans/B-report.md`, PR #2. All keys C requested are computed
(`summary.json` 32 keys + 28 in `summary-pending.json` until C adds them to SCHEMA). Open for B: only B9 (outside person).

**Group 2 (21/11 evening):** the leader accepted PR #4's group-2 runs. B7 is reopened for G2a and G2b only; every
earlier dataset stays frozen and untouched. G2 outputs go to `results/round3/g2close/` and `results/round3/g2layer/`. B7 was
re-declared on 22/11 after both finished.

**Group 3 (issue #7, 22/11):** four new runs requested by the leader; B7 reopened for G3a–G3d only (earlier data untouched).
User decision 22/11: two-day speedrun, device-free work first, runs from 22/11 23:59 (emulator chain + phone in parallel).
| Task | Card | Status |
|---|---|---|
| G3a + G3b (close2, fence-abort, capture + marker; 5 arms × 90) | `plans/g3race-card.md` | DONE 22/11 (final 0–1 + final-r2 2–9; 450 analysed; outcome in card §6; audit exploratory) |
| G3c (AirGuard, withdrawal mid-upload; 4 builds × 30) | `plans/g3app-card.md` | GATE FAIL 22/11 (calibration, v3; harness fault; v4 needs a new pilot) |
| G3d (phone cost; 3 arms × 3 sizes × 20 cells) | `plans/g3cost-card.md` | READY, not run (phone; on the user's request) |
