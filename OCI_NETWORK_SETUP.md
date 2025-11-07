# 🌐 OCI Network Configuration Guide

Complete network setup to ensure:
1. ✅ VM can access TwelveLabs API (outbound internet)
2. ✅ VM can access Oracle Autonomous Database (private/public endpoint)
3. ✅ VM is accessible from internet (inbound HTTP/HTTPS)
4. ✅ Proper security and firewall rules

---

## 📋 Network Architecture

```
                    Internet
                       ↕
    ┌──────────────────────────────────────┐
    │         Internet Gateway             │
    └──────────────┬───────────────────────┘
                   │
    ┌──────────────▼───────────────────────┐
    │   Virtual Cloud Network (VCN)        │
    │   CIDR: 10.0.0.0/16                  │
    └──────────────┬───────────────────────┘
                   │
    ┌──────────────▼───────────────────────┐
    │   Public Subnet (10.0.1.0/24)        │
    │   • Internet Gateway attached        │
    │   • Security List configured         │
    │   • Route Table to Internet Gateway  │
    └──────────────┬───────────────────────┘
                   │
    ┌──────────────▼───────────────────────┐
    │   Compute VM (Data Guardian)         │
    │   • Public IP: assigned              │
    │   • Private IP: 10.0.1.x             │
    │   • UFW Firewall: enabled            │
    └──────────────┬───────────────────────┘
                   │
         ┌─────────┼─────────┐
         │         │         │
         ▼         ▼         ▼
    Oracle DB   TwelveLabs  Object
    (mTLS)      API (HTTPS) Storage
```

---

## 🏗️ Step-by-Step Network Setup

### Step 1: Create VCN (Virtual Cloud Network)

If you don't have a VCN, create one:

**Via OCI Console:**
1. Navigate to **Networking** > **Virtual Cloud Networks**
2. Click **Start VCN Wizard**
3. Select **VCN with Internet Connectivity**
4. Configure:
   ```
   VCN Name: dataguardian-vcn
   VCN CIDR Block: 10.0.0.0/16
   Public Subnet CIDR: 10.0.1.0/24
   Private Subnet CIDR: 10.0.2.0/24 (optional)
   ```
5. Click **Next** and **Create**

This automatically creates:
- ✅ VCN with CIDR 10.0.0.0/16
- ✅ Public subnet with Internet Gateway
- ✅ Private subnet with NAT Gateway (optional)
- ✅ Service Gateway (for Oracle services)
- ✅ Route tables
- ✅ Default security lists

---

### Step 2: Configure Security Lists (Firewall Rules)

Security Lists control traffic to/from your VM.

#### 2.1 Ingress Rules (Inbound Traffic)

Navigate to: **VCN** > **Security Lists** > **Default Security List for dataguardian-vcn**

Add these ingress rules:

| Source CIDR | Protocol | Source Port | Dest Port | Description |
|-------------|----------|-------------|-----------|-------------|
| `0.0.0.0/0` | TCP | All | 22 | SSH access |
| `0.0.0.0/0` | TCP | All | 80 | HTTP |
| `0.0.0.0/0` | TCP | All | 443 | HTTPS |
| `0.0.0.0/0` | ICMP | - | Type 3, Code 4 | Path MTU Discovery |

**Important**: The `0.0.0.0/0` allows access from anywhere. For production:
- Restrict SSH (port 22) to your office/home IP
- Keep HTTP/HTTPS open for public access

#### 2.2 Egress Rules (Outbound Traffic)

**CRITICAL**: Ensure egress rules allow outbound traffic!

Default egress rule should exist:

| Destination CIDR | Protocol | Dest Port | Description |
|------------------|----------|-----------|-------------|
| `0.0.0.0/0` | All | All | Allow all outbound |

If missing, add this rule:
```
Destination CIDR: 0.0.0.0/0
IP Protocol: All Protocols
Destination Port Range: All
```

This enables:
- ✅ TwelveLabs API access (api.twelvelabs.io)
- ✅ Oracle Database access (if using public endpoint)
- ✅ Package downloads (apt, pip)
- ✅ Git operations
- ✅ DNS resolution

---

### Step 3: Verify Route Tables

Route tables direct traffic flow.

**Public Subnet Route Table** should have:

| Destination CIDR | Target | Description |
|------------------|--------|-------------|
| `0.0.0.0/0` | Internet Gateway | Route to internet |
| Service Network CIDR | Service Gateway | Route to OCI services |

**To verify:**
1. Navigate to **VCN** > **Route Tables**
2. Click on route table for public subnet
3. Ensure rule exists: `0.0.0.0/0` → Internet Gateway

---

### Step 4: Configure Network Security Groups (Optional but Recommended)

NSGs provide more granular control than Security Lists.

**Create NSG for Data Guardian:**

1. Navigate to **VCN** > **Network Security Groups**
2. Click **Create Network Security Group**
3. Name: `dataguardian-nsg`
4. Add rules:

**Ingress Rules:**
```
Source: 0.0.0.0/0, Protocol: TCP, Destination: 22 (SSH)
Source: 0.0.0.0/0, Protocol: TCP, Destination: 80 (HTTP)
Source: 0.0.0.0/0, Protocol: TCP, Destination: 443 (HTTPS)
```

**Egress Rules:**
```
Destination: 0.0.0.0/0, Protocol: All
```

5. Attach NSG to your VM:
   - **Compute** > **Instances** > Your VM
   - **Edit** > **Network Security Groups**
   - Select `dataguardian-nsg`

---

### Step 5: Verify Internet Gateway

Ensure Internet Gateway is attached:

1. Navigate to **VCN** > **Internet Gateways**
2. Verify status: **Available**
3. Ensure it's attached to your VCN

---

### Step 6: Assign Public IP to VM

When creating the VM:

**Networking Configuration:**
- **VCN**: dataguardian-vcn
- **Subnet**: Public Subnet (NOT private subnet)
- **Public IPv4 Address**: ✅ Assign a public IPv4 address
- **Private IPv4 Address**: Automatic

**If VM already exists without public IP:**
1. Create a **Reserved Public IP**:
   - **Networking** > **IP Management** > **Reserved Public IPs**
   - Click **Reserve Public IP Address**
2. Attach to VM:
   - **Compute** > **Instances** > Your VM
   - **Attached VNICs** > Click VNIC
   - **Resources** > **IPv4 Addresses**
   - Click **⋮** > **Edit** > Select reserved IP

---

## 🔒 Step 7: Configure VM Firewall (UFW)

Even with OCI Security Lists, configure OS-level firewall.

**The setup script already does this**, but verify:

```bash
# Check UFW status
sudo ufw status verbose

# Should show:
Status: active
To                         Action      From
--                         ------      ----
22/tcp                     ALLOW       Anywhere
80/tcp                     ALLOW       Anywhere
443/tcp                    ALLOW       Anywhere
22/tcp (v6)                ALLOW       Anywhere (v6)
80/tcp (v6)                ALLOW       Anywhere (v6)
443/tcp (v6)               ALLOW       Anywhere (v6)
```

**If not configured:**
```bash
sudo ufw --force enable
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw reload
```

---

## ✅ Step 8: Verify Connectivity

### 8.1 Test Outbound Internet Access

```bash
# SSH to VM
ssh ubuntu@YOUR_VM_IP

# Test DNS resolution
nslookup google.com
nslookup api.twelvelabs.io

# Test HTTP connectivity
curl -I https://www.google.com
curl -I https://api.twelvelabs.io

# Test package installation
sudo apt update

# Test pip
pip3 install --upgrade pip
```

**Expected Result**: All commands should succeed.

**If fails**: Check egress rules in Security List.

### 8.2 Test TwelveLabs API Access

```bash
# Test TwelveLabs API
export TWELVE_LABS_API_KEY="your_api_key"

curl -X GET "https://api.twelvelabs.io/v1.2/indexes" \
  -H "x-api-key: $TWELVE_LABS_API_KEY" \
  -H "Content-Type: application/json"
```

**Expected Result**: JSON response with your indexes.

**If fails**: 
- Check egress rules allow HTTPS (port 443)
- Verify API key is correct
- Check if VM can resolve DNS

### 8.3 Test Oracle Database Access

**If using public endpoint:**
```bash
# Test connectivity (replace with your connection string)
python3 << EOF
import oracledb
oracledb.init_oracle_client(lib_dir="/opt/oracle/instantclient_21_9")

try:
    conn = oracledb.connect(
        user="ADMIN",
        password="your_password",
        dsn="your_connection_string_high",
        config_dir="/home/dataguardian/TwelvelabsWithOracleVector/twelvelabvideoai/wallet",
        wallet_location="/home/dataguardian/TwelvelabsWithOracleVector/twelvelabvideoai/wallet",
        wallet_password="your_wallet_password"
    )
    print("✓ Database connection successful!")
    conn.close()
except Exception as e:
    print(f"✗ Connection failed: {e}")
EOF
```

**Expected Result**: "Database connection successful!"

### 8.4 Test Inbound Access from Internet

**From your local machine:**

```bash
# Test HTTP access
curl -I http://YOUR_VM_IP

# Test with browser
open http://YOUR_VM_IP

# Test specific port
nc -zv YOUR_VM_IP 80
nc -zv YOUR_VM_IP 443
```

**Expected Result**: Connection succeeds, see Nginx welcome or app page.

**If fails**:
- Check VM has public IP: `curl ifconfig.me` (run on VM)
- Check Security List ingress rules allow port 80/443
- Check UFW allows port 80/443
- Check application is running: `sudo systemctl status dataguardian`

---

## 🔍 Troubleshooting Network Issues

### Issue 1: Cannot Access TwelveLabs API

**Symptoms**: `curl` to api.twelvelabs.io fails, pip install fails

**Check:**
```bash
# 1. Test DNS resolution
nslookup api.twelvelabs.io
# Should return IP address

# 2. Test internet connectivity
ping -c 4 8.8.8.8
# Should succeed

# 3. Check routing
ip route
# Should show default route via Internet Gateway

# 4. Test HTTPS
curl -v https://api.twelvelabs.io
# Should connect (even if 401 unauthorized)
```

**Fix:**
1. Verify egress rule in Security List allows `0.0.0.0/0` all protocols
2. Check Route Table has route to Internet Gateway
3. Verify Internet Gateway is attached and enabled
4. Check UFW: `sudo ufw status` (should allow outgoing)

### Issue 2: Cannot Access VM from Internet

**Symptoms**: Cannot SSH or access HTTP from your computer

**Check:**
```bash
# On VM
curl ifconfig.me  # Should show public IP

# From local machine
ping YOUR_VM_IP
curl -I http://YOUR_VM_IP
```

**Fix:**
1. Verify VM is in **public subnet** (not private)
2. Check VM has **public IP assigned**
3. Verify ingress rules in Security List allow ports 22/80/443 from `0.0.0.0/0`
4. Check UFW on VM: `sudo ufw status`
5. Verify application is running: `sudo systemctl status dataguardian nginx`

### Issue 3: VM Can Ping but Cannot Use Services

**Symptoms**: Ping works, but HTTP/HTTPS fails

**Check:**
```bash
# On VM
sudo netstat -tuln | grep :80
sudo netstat -tuln | grep :443
# Should show Nginx listening

sudo systemctl status nginx
sudo systemctl status dataguardian
# Should show active (running)
```

**Fix:**
1. Start services: `sudo systemctl start nginx dataguardian`
2. Check Nginx logs: `sudo tail -f /var/log/nginx/error.log`
3. Check application logs: `sudo journalctl -u dataguardian -n 50`

### Issue 4: Oracle Database Connection Fails

**Symptoms**: Application starts but database queries fail

**Check:**
```bash
# 1. Verify wallet files
ls -la /home/dataguardian/TwelvelabsWithOracleVector/twelvelabvideoai/wallet/
# Should see: cwallet.sso, tnsnames.ora, sqlnet.ora

# 2. Check connection string
cat /home/dataguardian/TwelvelabsWithOracleContract/.env | grep ORACLE

# 3. Test with sqlplus (if installed)
sqlplus ADMIN@your_connection_string_high
```

**Fix:**
1. If using **private endpoint**: Ensure VM can access private subnet (needs VCN peering or VPN)
2. If using **public endpoint**: Verify egress rules allow HTTPS to Oracle domains
3. Check wallet files are correct and not corrupted
4. Verify credentials in `.env` file

---

## 📊 Network Configuration Checklist

Use this checklist to verify your setup:

### VCN Configuration
- [ ] VCN created with appropriate CIDR (e.g., 10.0.0.0/16)
- [ ] Public subnet exists (e.g., 10.0.1.0/24)
- [ ] Internet Gateway created and attached
- [ ] Service Gateway created (for Oracle services)

### Route Tables
- [ ] Public subnet route table has rule: `0.0.0.0/0` → Internet Gateway
- [ ] Route to Service Gateway for Oracle services (optional)

### Security Lists
- [ ] Ingress rule: 0.0.0.0/0 → TCP port 22 (SSH)
- [ ] Ingress rule: 0.0.0.0/0 → TCP port 80 (HTTP)
- [ ] Ingress rule: 0.0.0.0/0 → TCP port 443 (HTTPS)
- [ ] Egress rule: `0.0.0.0/0` → All protocols (allows outbound)

### VM Configuration
- [ ] VM deployed in public subnet
- [ ] Public IP address assigned
- [ ] Security List attached to subnet
- [ ] NSG attached to VM (optional)

### OS Firewall (UFW)
- [ ] UFW enabled
- [ ] Port 22 allowed (SSH)
- [ ] Port 80 allowed (HTTP)
- [ ] Port 443 allowed (HTTPS)
- [ ] Default outgoing: ALLOW

### Application Configuration
- [ ] Nginx listening on port 80
- [ ] Gunicorn listening on 127.0.0.1:8080
- [ ] Services running (dataguardian, nginx)
- [ ] `.env` file has TwelveLabs API key
- [ ] Database wallet files in correct location

### Connectivity Tests
- [ ] Can SSH to VM from internet
- [ ] Can access HTTP from internet (http://VM_IP)
- [ ] VM can curl https://api.twelvelabs.io
- [ ] VM can access Oracle Database
- [ ] VM can apt update / pip install (internet access)
- [ ] Application responds to health check

---

## 🎯 Production Best Practices

### Security Hardening

1. **Restrict SSH Access**
   ```bash
   # In Security List, change SSH rule from:
   Source: 0.0.0.0/0
   # To your office IP:
   Source: YOUR_OFFICE_IP/32
   ```

2. **Use Bastion Host** (for sensitive environments)
   - Deploy bastion host in public subnet
   - Move application VM to private subnet
   - SSH via bastion only

3. **Enable DDoS Protection**
   - OCI provides automatic DDoS protection
   - Consider WAF (Web Application Firewall) for additional security

4. **Use Reserved Public IP**
   - Prevents IP change on VM restart
   - Easier for DNS configuration

### Monitoring

1. **Enable VCN Flow Logs**
   ```
   VCN → Flow Logs → Enable
   ```
   Track all network traffic for security and debugging

2. **Setup Alarms**
   - Alert on high egress traffic (potential data exfiltration)
   - Alert on failed SSH attempts
   - Alert on service downtime

---

## 📞 Support

If network issues persist:

1. **OCI Support**: [Open Service Request](https://support.oracle.com/)
2. **Check OCI Status**: [status.oracle.com](https://status.oracle.com/)
3. **Community Forums**: [Oracle Cloud Community](https://cloudcustomerconnect.oracle.com/)

---

**Network Setup Time**: ~15 minutes  
**Difficulty**: Intermediate

✅ **Your VM is now properly networked for production use!**
