# Receiver mode B (EC2) — for test 1 on phones (real-phone-pending #1)

`artifact/devicefarm/README.md` (C): test 1 on a real phone needs the receiver on an EC2 host in us-west-2 so the phone
uses a real network path. Files here (B):
- `../../../followup/receiver_b.py`: TLS 8798 / plain 8799 receivers (same log format as the suites) + control API on 8800
  (token): link profile via `tc` (edge/umts/lte/full, emulator presets; ingress via ifb), stall mode, log download.
  Tested locally on the Mac with `--no-tc` (19/11).
- `setup.sh` (dry by default; `--create` makes t3.micro + security group + key pair; **user go-ahead required, costs
  money, < 10 USD for the round**), `start.sh <ip>` (fresh cert with SAN = IP, token in ~/.p04/ec2, starts the receiver),
  `teardown.sh <instance-id>` (terminate + clean up). Nothing here stores secrets in the repository.
- Harness side (after B10 has run, so its frozen harness is not touched): `race_suite.py` option for a remote receiver
  (`--receiver http://IP:8800 --token … --host IP --no-root`), shaping through the control API instead of `adb emu`.
