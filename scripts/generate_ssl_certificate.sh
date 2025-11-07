#!/bin/bash
# Generate Self-Signed SSL Certificate for Flask Application
# Date: November 8, 2025

echo "🔐 SSL Certificate Generator for Flask Application"
echo "=================================================="
echo ""

# Create ssl directory if it doesn't exist
SSL_DIR="../ssl"
mkdir -p "$SSL_DIR"

# Certificate details
COUNTRY="US"
STATE="California"
CITY="San Francisco"
ORG="DataGuardian"
ORG_UNIT="IT Department"
COMMON_NAME="localhost"
EMAIL="admin@dataguardian.local"
DAYS_VALID=365

echo "📋 Certificate Configuration:"
echo "   Common Name: $COMMON_NAME"
echo "   Organization: $ORG"
echo "   Valid for: $DAYS_VALID days"
echo ""

# Generate private key
echo "🔑 Step 1/3: Generating private key..."
openssl genrsa -out "$SSL_DIR/private.key" 2048 2>/dev/null
if [ $? -eq 0 ]; then
    echo "   ✅ Private key generated: ssl/private.key"
else
    echo "   ❌ Failed to generate private key"
    exit 1
fi

# Generate certificate signing request (CSR)
echo "📝 Step 2/3: Generating certificate signing request..."
openssl req -new -key "$SSL_DIR/private.key" -out "$SSL_DIR/certificate.csr" \
    -subj "/C=$COUNTRY/ST=$STATE/L=$CITY/O=$ORG/OU=$ORG_UNIT/CN=$COMMON_NAME/emailAddress=$EMAIL" \
    2>/dev/null

if [ $? -eq 0 ]; then
    echo "   ✅ CSR generated: ssl/certificate.csr"
else
    echo "   ❌ Failed to generate CSR"
    exit 1
fi

# Generate self-signed certificate with SAN (Subject Alternative Names)
echo "🎫 Step 3/3: Generating self-signed certificate..."

# Create temporary OpenSSL config with SAN
cat > "$SSL_DIR/openssl.cnf" << EOF
[req]
default_bits = 2048
prompt = no
default_md = sha256
distinguished_name = dn
req_extensions = v3_req

[dn]
C=$COUNTRY
ST=$STATE
L=$CITY
O=$ORG
OU=$ORG_UNIT
emailAddress=$EMAIL
CN=$COMMON_NAME

[v3_req]
subjectAltName = @alt_names

[alt_names]
DNS.1 = localhost
DNS.2 = 127.0.0.1
DNS.3 = ::1
IP.1 = 127.0.0.1
IP.2 = ::1
EOF

openssl x509 -req -in "$SSL_DIR/certificate.csr" \
    -signkey "$SSL_DIR/private.key" \
    -out "$SSL_DIR/certificate.crt" \
    -days $DAYS_VALID \
    -extensions v3_req \
    -extfile "$SSL_DIR/openssl.cnf" \
    2>/dev/null

if [ $? -eq 0 ]; then
    echo "   ✅ Certificate generated: ssl/certificate.crt"
else
    echo "   ❌ Failed to generate certificate"
    exit 1
fi

# Clean up temporary files
rm "$SSL_DIR/certificate.csr"
rm "$SSL_DIR/openssl.cnf"

# Set proper permissions
chmod 600 "$SSL_DIR/private.key"
chmod 644 "$SSL_DIR/certificate.crt"

echo ""
echo "✅ SSL Certificate Generation Complete!"
echo ""
echo "📂 Generated Files:"
echo "   - ssl/private.key      (Private key - keep secure!)"
echo "   - ssl/certificate.crt  (Public certificate)"
echo ""
echo "📅 Certificate Details:"
openssl x509 -in "$SSL_DIR/certificate.crt" -noout -subject -dates -issuer 2>/dev/null
echo ""
echo "🔍 To view full certificate details:"
echo "   openssl x509 -in ssl/certificate.crt -text -noout"
echo ""
echo "🚀 Next Steps:"
echo "   1. Update .env file with SSL settings"
echo "   2. Run Flask app with SSL: python src/localhost_only_flask.py"
echo "   3. Access via: https://localhost:8443"
echo ""
echo "⚠️  Browser Warning:"
echo "   Your browser will show a security warning because this is"
echo "   a self-signed certificate. Click 'Advanced' and 'Proceed to"
echo "   localhost' to continue."
echo ""

# Display fingerprint
echo "🔐 Certificate Fingerprint:"
openssl x509 -in "$SSL_DIR/certificate.crt" -noout -fingerprint -sha256 2>/dev/null
echo ""
