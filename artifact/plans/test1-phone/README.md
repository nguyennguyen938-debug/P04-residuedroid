# Test 1 on the user's own Android 15 phone — run sheet (card: `plans/test1-phone-card.md`)

Order (B runs every command; the user does the steps marked USER):
1. USER: phone on USB, Developer options → USB debugging on (and "Install via USB" where the OEM has it), accept the Mac's
   RSA prompt, charger on, "Stay awake" on, network chosen (Wi-Fi or mobile data) and left unchanged.
2. `plans/test1-phone/preflight_phone.sh <serial>` → `PREFLIGHT OK` (read-only; installs the test APK only).
3. USER confirms EC2 creation, then `AWS_REGION=<region> plans/test6/ec2/setup.sh --create` (t3.micro, < 10 USD), then
   `PROFILE_SET=b10v3 plans/test6/ec2/start.sh <ip>` (token stays in ~/.p04/ec2, never in the repo or logs).
4. Commit the card. `plans/test1-phone/run_phone.sh pilot <ip> <serial>` (~20 min) → gate + N from the card's rule.
5. Write N under "Pilot" in the card, commit. `plans/test1-phone/run_phone.sh final <ip> <serial> <blocks>` (~1.5–2 h at 10 blocks).
6. Close-out: `plans/test1-phone/cleanup_phone.sh <serial>` (uninstalls the app, removes the CA file);
   `AWS_REGION=<region> plans/test6/ec2/teardown.sh <instance-id>`; RUNLOG entries; card §6; EXCLUSIONS/PROTOCOL; summary.json if C adds keys.
