# 🚀 Automated OCI Deployment - Quick Start

## Current Status

✅ **OCI Configuration** - Ready  
✅ **OCI Private Key** - Found  
✅ **SSH Keys** - Generated  
✅ **Database Wallet** - Found  
⚠️ **Environment Configuration** - Needs your passwords  
✅ **Deployment Scripts** - Ready

---

## 📝 Step-by-Step Deployment

### Step 1: Configure Credentials (2 minutes)

You need to add 3 passwords to the `.env` file:

```bash
# Open .env file in your editor
nano twelvelabvideoai/.env

# OR use VS Code
code twelvelabvideoai/.env
```

**Fill in these values:**

1. **ORACLE_DB_PASSWORD** - Your Oracle ADB ADMIN password
2. **ORACLE_DB_WALLET_PASSWORD** - Password you set when downloading wallet
3. **TWELVE_LABS_API_KEY** - Get from https://dashboard.twelvelabs.io/

**Note**: Connection string is already set to `ocdmrealtime_high`

### Step 2: Verify Configuration

```bash
./scripts/pre_deployment_check.sh
```

This will verify:
- ✅ All credentials are filled in
- ✅ OCI config is valid
- ✅ SSH keys exist
- ✅ Wallet files are present
- ✅ Scripts are executable

### Step 3: Run Deployment (10-15 minutes)

```bash
./scripts/oci_full_deployment.sh
```

This automated script will:

1. **Install OCI CLI** (if not present)
   - Uses Homebrew on macOS
   - Takes ~2 minutes

2. **Create VCN and Networking**
   - Create Virtual Cloud Network (10.0.0.0/16)
   - Create Internet Gateway
   - Configure Route Table (0.0.0.0/0 → IGW)
   - Create Security List (ingress: 22,80,443 | egress: all)
   - Create Public Subnet (10.0.1.0/24)

3. **Create Compute Instance**
   - VM Name: dataguardian-app-server
   - Shape: VM.Standard.E4.Flex (2 OCPUs, 16GB RAM)
   - Image: Ubuntu 22.04 LTS
   - Assign public IP
   - Takes ~3 minutes

4. **Wait for SSH Access**
   - Polls SSH until available
   - Takes ~1-2 minutes

5. **Upload Configuration Files**
   - Database wallet → VM
   - .env configuration → VM

6. **Run System Setup**
   - Update system packages
   - Install Python 3.11, FFmpeg, Nginx
   - Install Oracle Instant Client
   - Configure firewall (UFW)
   - Pre-flight network checks
   - Takes ~5 minutes

7. **Deploy Application**
   - Clone repository
   - Create Python virtual environment
   - Install dependencies
   - Configure Gunicorn (WSGI server)
   - Create systemd service
   - Configure Nginx reverse proxy
   - Start services
   - Takes ~3 minutes

---

## 🎯 After Deployment

### Access Your Application

Once deployment completes, you'll see:

```
═══════════════════════════════════════════════════════════
  Data Guardian Application Successfully Deployed
═══════════════════════════════════════════════════════════

  🌐 Application URL: http://YOUR_VM_IP
  🔒 HTTPS URL: https://YOUR_VM_IP (after SSL setup)
  📊 Server IP: YOUR_VM_IP
  🖥️  VM Name: dataguardian-app-server
  📍 Region: us-ashburn-1
```

### Test the Application

```bash
# From your local machine
curl http://YOUR_VM_IP

# Or open in browser
open http://YOUR_VM_IP
```

### Setup SSL (Optional but Recommended)

```bash
# SSH to VM
ssh -i ~/.ssh/id_rsa ubuntu@YOUR_VM_IP

# Setup SSL with your domain
sudo /home/dataguardian/TwelvelabsWithOracleVector/scripts/manage.sh ssl-setup your-domain.com
```

### Management Commands

SSH to your VM and use the management script:

```bash
ssh -i ~/.ssh/id_rsa ubuntu@YOUR_VM_IP

# Switch to dataguardian user
sudo su - dataguardian
cd TwelvelabsWithOracleVector

# Common commands
./scripts/manage.sh status      # Show service status
./scripts/manage.sh logs        # View application logs
./scripts/manage.sh restart     # Restart application
./scripts/manage.sh health      # System health check
./scripts/manage.sh update      # Update from git
./scripts/manage.sh stats       # System statistics
```

---

## 🔧 Troubleshooting

### Deployment Failed?

**Check logs:**
```bash
# View deployment script output (scroll up in terminal)
# Or re-run with verbose output:
bash -x ./scripts/oci_full_deployment.sh
```

**Common issues:**

1. **OCI CLI installation failed**
   - Install manually: `brew install oci-cli`
   - Or follow: https://docs.oracle.com/en-us/iaas/Content/API/SDKDocs/cliinstall.htm

2. **Cannot create VM (quota exceeded)**
   - Check OCI Console → Governance → Limits
   - Request limit increase or use different region

3. **SSH connection timeout**
   - Verify Security List allows port 22 from your IP
   - Check VM is in RUNNING state: OCI Console → Compute → Instances
   - Wait a bit longer (sometimes takes 2-3 minutes)

4. **Network connectivity issues on VM**
   - See: [OCI_NETWORK_SETUP.md](../OCI_NETWORK_SETUP.md)
   - Verify egress rules allow 0.0.0.0/0
   - Check Internet Gateway is attached
   - Verify route table: 0.0.0.0/0 → IGW

5. **Application won't start**
   - SSH to VM: `ssh -i ~/.ssh/id_rsa ubuntu@YOUR_VM_IP`
   - Check logs: `sudo journalctl -u dataguardian -n 50`
   - Verify .env has all credentials filled
   - Test database: `sudo su - dataguardian`, then run test script

### Need to Redeploy?

**Destroy VM and start fresh:**
```bash
# Find instance OCID
oci compute instance list --compartment-id YOUR_COMPARTMENT_ID

# Terminate instance
oci compute instance terminate --instance-id YOUR_INSTANCE_OCID --force

# Re-run deployment
./scripts/oci_full_deployment.sh
```

---

## 📊 What Gets Created

### OCI Resources

| Resource | Name | Purpose |
|----------|------|---------|
| VCN | dataguardian-vcn | Virtual network (10.0.0.0/16) |
| Internet Gateway | dataguardian-vcn-igw | Internet connectivity |
| Route Table | dataguardian-vcn-rt | Routing to internet |
| Security List | dataguardian-vcn-seclist | Firewall rules |
| Public Subnet | dataguardian-public-subnet | VM network (10.0.1.0/24) |
| Compute Instance | dataguardian-app-server | VM (2 OCPUs, 16GB RAM) |

### VM Software Stack

| Component | Version/Config | Purpose |
|-----------|---------------|---------|
| Ubuntu | 22.04 LTS | Operating system |
| Python | 3.11 | Application runtime |
| Nginx | Latest | Reverse proxy, SSL termination |
| Gunicorn | Latest | WSGI server (workers = 5) |
| Flask | 2.3+ | Web framework |
| FFmpeg | Latest | Video processing |
| Oracle Instant Client | 21.9 | Database connectivity |
| UFW | Enabled | OS-level firewall |

### Application Services

| Service | Status | Auto-start |
|---------|--------|------------|
| dataguardian.service | systemd | ✅ Enabled |
| nginx.service | systemd | ✅ Enabled |

---

## 💰 Cost Estimate

**Monthly OCI costs (us-ashburn-1):**

- VM.Standard.E4.Flex (2 OCPUs, 16GB RAM): ~$80/month
- Public IP: $0.01/hour = ~$7/month
- VCN, Internet Gateway, Route Table: Free
- Data Transfer (first 10TB outbound): Free
- Oracle Autonomous Database: (separate, already provisioned)
- OCI Object Storage: (separate, already provisioned)

**Total estimated cost: ~$87/month**

**Ways to reduce cost:**
- Use smaller shape (1 OCPU, 8GB RAM): ~$40/month
- Use ARM-based shape (A1.Flex): Free tier eligible
- Schedule VM to stop during off-hours
- Use preemptible instances: 50% discount

---

## 🔒 Security Best Practices

After deployment:

1. **Restrict SSH Access**
   - Edit Security List to allow SSH only from your IP
   - Don't use 0.0.0.0/0 for port 22 in production

2. **Setup SSL Certificate**
   - Use Let's Encrypt (free)
   - Run: `./scripts/manage.sh ssl-setup your-domain.com`

3. **Enable Monitoring**
   - OCI Console → Monitoring → Alarms
   - Create alarms for CPU, memory, disk usage

4. **Regular Updates**
   - Schedule weekly: `sudo apt update && sudo apt upgrade -y`
   - Update application: `./scripts/manage.sh update`

5. **Backup Configuration**
   - Backup .env file securely
   - Backup database wallet
   - Create VM snapshots monthly

---

## 📞 Support

**Documentation:**
- Full Deployment Guide: [OCI_DEPLOYMENT_GUIDE.md](../OCI_DEPLOYMENT_GUIDE.md)
- Network Setup: [OCI_NETWORK_SETUP.md](../OCI_NETWORK_SETUP.md)
- Feature Documentation: [ADVANCED_FEATURES.md](../ADVANCED_FEATURES.md)

**Quick Commands:**
```bash
# Pre-deployment check
./scripts/pre_deployment_check.sh

# Full deployment
./scripts/oci_full_deployment.sh

# Configure .env
./scripts/configure_env.sh

# SSH to VM
ssh -i ~/.ssh/id_rsa ubuntu@YOUR_VM_IP
```

---

**Ready to deploy? Follow Step 1 above!** 🚀
