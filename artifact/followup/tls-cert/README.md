# Local TLS test certificate

The test private key is intentionally excluded from Git and public archives.
Before running `artifact/followup/tls_suite.py`, generate a fresh local certificate
and key from the project root (OpenSSL with `-addext` support):

```sh
openssl req -x509 -newkey rsa:2048 -nodes -days 30 \
  -keyout artifact/followup/tls-cert/test-key.pem \
  -out artifact/followup/tls-cert/test-ca.pem \
  -subj '/CN=10.0.2.2' \
  -addext 'subjectAltName=IP:10.0.2.2,IP:127.0.0.1,DNS:localhost'
chmod 600 artifact/followup/tls-cert/test-key.pem
```

The harness loads this certificate on the receiver and installs the matching
certificate into the test app. These are local fixture credentials only; do not
use them for a production service. The archived certificate and raw outcomes
identify the recorded experiment; a new live run uses the freshly generated pair.
