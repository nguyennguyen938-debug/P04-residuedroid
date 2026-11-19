#!/bin/bash
# Copy receiver_b.py and a fresh certificate (SAN = the instance IP) to the EC2 host and start it. Token stays local.
# Usage: start.sh <ip>   (writes the token to ~/.p04/ec2/token)
set -euo pipefail
main() {
IP=$1; HERE=$(cd "$(dirname "$0")" && pwd); ART=$(cd "$HERE/../../.." && pwd); K=~/.p04/ec2/p04-receiver.pem; C=~/.p04/ec2/cert-$IP
mkdir -p "$C"; openssl req -x509 -newkey rsa:2048 -nodes -days 30 -keyout "$C/test-key.pem" -out "$C/test-ca.pem" -subj "/CN=$IP" \
  -addext "subjectAltName=IP:$IP" 2>/dev/null; chmod 600 "$C/test-key.pem"
TOKEN=$(openssl rand -hex 16); echo "$TOKEN" > ~/.p04/ec2/token; chmod 600 ~/.p04/ec2/token
scp -i "$K" -o StrictHostKeyChecking=accept-new "$ART/followup/receiver_b.py" "$C/test-ca.pem" "$C/test-key.pem" ec2-user@"$IP":/tmp/
ssh -i "$K" ec2-user@"$IP" "sudo mkdir -p /opt/p04/cert && sudo mv /tmp/receiver_b.py /opt/p04/ && sudo mv /tmp/test-*.pem /opt/p04/cert/ && \
  sudo nohup python3 /opt/p04/receiver_b.py --cert /opt/p04/cert --dev \$(ip route show default | awk '{print \$5}') --token $TOKEN --out /var/p04/receiver > /var/tmp/receiver_b.log 2>&1 &"
sleep 3; curl -s -H "X-Token: $TOKEN" "http://$IP:8800/" && echo " (receiver up; CA for the phone: $C/test-ca.pem)"
}
main "$@"; exit $?
