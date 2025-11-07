#!/bin/bash
#
# Script to add port 8443 ingress rule to OCI Security List
# Run this after configuring OCI CLI with: oci setup config
#

set -e

echo "🔍 Finding Security List for your instance..."

# Instance OCID (from metadata)
INSTANCE_OCID="ocid1.instance.oc1.iad.anuwcljsy5l3z3yc2j33kmfltb67pk4ohgov7xazhx6slvx5qetvskczlrqq"
COMPARTMENT_OCID="ocid1.compartment.oc1..aaaaaaaaipofyxb7s2xmwe3j3skrccrj6yek6lgtlkekguzqlr2mlgyt54iq"

echo "📋 Instance: $INSTANCE_OCID"
echo "📦 Compartment: $COMPARTMENT_OCID"

# Get VNIC attachment
echo ""
echo "🔍 Getting VNIC details..."
VNIC_ATTACHMENT=$(oci compute vnic-attachment list \
  --compartment-id "$COMPARTMENT_OCID" \
  --instance-id "$INSTANCE_OCID" \
  --query 'data[0]."vnic-id"' \
  --raw-output)

echo "✅ VNIC ID: $VNIC_ATTACHMENT"

# Get subnet from VNIC
echo ""
echo "🔍 Getting Subnet details..."
SUBNET_OCID=$(oci network vnic get \
  --vnic-id "$VNIC_ATTACHMENT" \
  --query 'data."subnet-id"' \
  --raw-output)

echo "✅ Subnet ID: $SUBNET_OCID"

# Get security list from subnet
echo ""
echo "🔍 Getting Security Lists..."
SECURITY_LIST_OCID=$(oci network subnet get \
  --subnet-id "$SUBNET_OCID" \
  --query 'data."security-list-ids"[0]' \
  --raw-output)

echo "✅ Security List ID: $SECURITY_LIST_OCID"

# Check if rule already exists
echo ""
echo "🔍 Checking if port 8443 rule already exists..."
EXISTING_RULE=$(oci network security-list get \
  --security-list-id "$SECURITY_LIST_OCID" \
  --query 'data."ingress-security-rules"[?destination-port-range."max" == `8443`]' 2>/dev/null || echo "[]")

if [[ "$EXISTING_RULE" != "[]" ]]; then
  echo "✅ Port 8443 ingress rule already exists!"
  echo "$EXISTING_RULE"
  exit 0
fi

# Add the ingress rule
echo ""
echo "➕ Adding ingress rule for port 8443..."

# Get current ingress rules
CURRENT_RULES=$(oci network security-list get \
  --security-list-id "$SECURITY_LIST_OCID" \
  --query 'data."ingress-security-rules"')

# Create new rule JSON
NEW_RULE='{
  "source": "0.0.0.0/0",
  "protocol": "6",
  "isStateless": false,
  "tcpOptions": {
    "destinationPortRange": {
      "min": 8443,
      "max": 8443
    }
  },
  "description": "HTTPS for DataGuardian Application"
}'

# Update security list
echo "$CURRENT_RULES" | python3 -c "
import sys, json
rules = json.load(sys.stdin)
new_rule = $NEW_RULE
rules.append(new_rule)
print(json.dumps(rules))
" > /tmp/updated_rules.json

oci network security-list update \
  --security-list-id "$SECURITY_LIST_OCID" \
  --ingress-security-rules file:///tmp/updated_rules.json \
  --force

echo ""
echo "✅ Security rule added successfully!"
echo ""
echo "🌐 You can now access your application at:"
echo "   https://150.136.235.189:8443"
echo ""
echo "⚠️  Browser will show security warning (self-signed certificate)"
echo "   Click 'Advanced' → 'Proceed to 150.136.235.189'"
