#!/bin/bash
# Receiver mode B on EC2 for Test 6 / test 1 on phones (plans/test6/ec2/README.md). Needs the user's go-ahead (costs money):
# this script only runs AWS calls when called with --create; without it, it prints what it would do.
# Usage: setup.sh [--create] ; then start.sh <ip> ; teardown.sh <instance-id>
set -euo pipefail
main() {
export AWS_PROFILE=${AWS_PROFILE:-p04} AWS_REGION=${AWS_REGION:-us-west-2}
HERE=$(cd "$(dirname "$0")" && pwd)
AMI=$(aws ssm get-parameter --name /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64 --query Parameter.Value --output text)
echo "plan: t3.micro, AMI $AMI, security group p04-receiver (tcp 8798, 8799 from 0.0.0.0/0; 8800 + 22 from this Mac's IP only), key pair p04-receiver"
[ "${1:-}" = --create ] || { echo "dry: pass --create to create (user go-ahead required)"; exit 0; }
MYIP=$(curl -s https://checkip.amazonaws.com)/32
SG=$(aws ec2 create-security-group --group-name p04-receiver --description "P04 receiver mode B" --query GroupId --output text)
aws ec2 authorize-security-group-ingress --group-id "$SG" --ip-permissions \
  "IpProtocol=tcp,FromPort=8798,ToPort=8799,IpRanges=[{CidrIp=0.0.0.0/0}]" \
  "IpProtocol=tcp,FromPort=8800,ToPort=8800,IpRanges=[{CidrIp=$MYIP}]" "IpProtocol=tcp,FromPort=22,ToPort=22,IpRanges=[{CidrIp=$MYIP}]"
mkdir -p ~/.p04/ec2 && aws ec2 create-key-pair --key-name p04-receiver --query KeyMaterial --output text > ~/.p04/ec2/p04-receiver.pem && chmod 600 ~/.p04/ec2/p04-receiver.pem
ID=$(aws ec2 run-instances --image-id "$AMI" --instance-type t3.micro --key-name p04-receiver --security-group-ids "$SG" \
  --user-data "file://$HERE/user-data.sh" --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=p04-receiver}]' --query 'Instances[0].InstanceId' --output text)
aws ec2 wait instance-running --instance-ids "$ID"
IP=$(aws ec2 describe-instances --instance-ids "$ID" --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)
echo "instance $ID ip $IP (record in RUNLOG; delete with teardown.sh $ID)"
}
main "$@"; exit $?
