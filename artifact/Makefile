# ResidueDroid artifact. `make all` regenerates every table/figure/macro from the recorded raw data and rebuilds the PDF.
# Runtime targets write to RERUN (default results/rerun), preserving recorded raw evidence.
# Start and configure your own AVDs; env.sh accepts explicit JAVA_HOME and ANDROID_HOME.
PY=python3
RERUN=results/rerun
all: paper
static:
	cd static && $(PY) -I static_summary.py >/dev/null
analyze: static
	$(PY) scripts/summarize.py >/dev/null
render: analyze
	$(PY) scripts/render.py
revision: render
	$(PY) revision/historical_uncertainty.py > results/revision-20261115/bootstrap.log
	$(PY) revision/oracle_v2.py results/revision-20261115
	$(PY) revision/matched_oracle.py
	$(PY) followup/matched_oracle.py
	$(PY) followup/deficit_causes.py
	$(PY) revision/render_revision.py
	$(PY) revision/audit_results.py > results/revision-20261115/evidence-audit.log
paper: revision
	$(PY) followup/analyze_tls.py > results/review-followup-20261115/transport-analysis.log
	$(PY) followup/render.py
	$(PY) scripts/render_tests.py
	bash ../manuscript/build.sh
apks:
	bash fixture/build.sh && bash acra/build.sh
campaign:
	$(PY) harness/campaign.py --serial emulator-5600 --avd P04AvdA --port 8787 --variants none,cancel,enqueue,jobstart,conv,rd --out $(RERUN)/c1/A --trials 50 &
	$(PY) harness/campaign.py --serial emulator-5602 --avd P04AvdB --port 8788 --variants egress,rd,volatile,taint --out $(RERUN)/c1/B --trials 50
micro:
	$(PY) harness/micro.py --serial emulator-5600 --out $(RERUN)/micro
acra:
	$(PY) harness/acra_case.py --serial emulator-5600 --avd P04AvdA --out $(RERUN)/acra --trials 30 --reboot-trials 10
substrates:
	$(PY) harness/campaign.py --serial emulator-5600 --avd P04AvdA --port 8792 --variants wmnone,wmconv,wmrd --out $(RERUN)/sub_work --schedules pending,kill,forcestop,reboot --trials 20 --substrate work --apkdir workmanager/build/apk &
	$(PY) harness/campaign.py --serial emulator-5602 --avd P04AvdB --port 8791 --variants alnone,alconv,alrd --out $(RERUN)/sub_alarm --schedules pending,kill,forcestop,reboot --start 5 --trials 20 --substrate alarm --apkdir fixture/build/apk_alarm
corpus:
	cd static && $(PY) -I select_corpus.py 300 && $(PY) -I download.py && $(PY) -I scan_corpus.py 4
.PHONY: all static analyze render revision paper apks campaign micro acra substrates corpus
