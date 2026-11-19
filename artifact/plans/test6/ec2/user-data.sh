#!/bin/bash
# EC2 user-data for receiver mode B (Amazon Linux 2023, us-west-2). Installs nothing beyond python3/iproute-tc, then waits
# for receiver_b.py + certificate to be copied by setup.sh. No secrets in this file; the control token is passed at start.
set -eux
dnf -y install python3 iproute-tc kernel-modules-extra || yum -y install python3 iproute-tc
mkdir -p /opt/p04 /var/p04
