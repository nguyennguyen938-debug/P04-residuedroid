#!/bin/bash
# Stop billing: terminate the receiver instance, then delete its security group and key pair. Usage: teardown.sh <instance-id>
set -euo pipefail
main() {
export AWS_PROFILE=${AWS_PROFILE:-p04} AWS_REGION=us-west-2
aws ec2 terminate-instances --instance-ids "$1" >/dev/null && aws ec2 wait instance-terminated --instance-ids "$1"
aws ec2 delete-security-group --group-name p04-receiver || true; aws ec2 delete-key-pair --key-name p04-receiver || true
echo "terminated $1; security group and key pair removed"
}
main "$@"; exit $?
