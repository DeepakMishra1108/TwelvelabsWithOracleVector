# Authentication System Deployment Guide

## Files to Deploy

1. **scripts/create_users_table.sql** - Database schema
2. **scripts/create_admin_user.py** - Admin user creation script
3. **requirements.txt** - Updated with auth packages
4. **twelvelabvideoai/src/auth_utils.py** - Authentication utilities
5. **twelvelabvideoai/src/templates/login.html** - Login page
6. **src/localhost_only_flask.py** - Updated Flask app with auth
7. **twelvelabvideoai/src/templates/index.html** - Updated with user menu

## Deployment Steps

### Step 1: Create Database Tables
```bash
# Upload SQL script to server
scp scripts/create_users_table.sql ubuntu@150.136.235.189:/tmp/

# Connect to Oracle DB and run script
# You can use SQL Developer or sqlcl
```

### Step 2: Install Python Packages
```bash
ssh ubuntu@150.136.235.189
cd /home/dataguardian/TwelvelabsWithOracleVector
source twelvelabvideoai/bin/activate
pip install flask-login bcrypt flask-wtf email-validator
```

### Step 3: Deploy Application Files
```bash
# Upload all files
scp src/localhost_only_flask.py ubuntu@150.136.235.189:/tmp/
scp twelvelabvideoai/src/auth_utils.py ubuntu@150.136.235.189:/tmp/
scp twelvelabvideoai/src/templates/login.html ubuntu@150.136.235.189:/tmp/
scp twelvelabvideoai/src/templates/index.html ubuntu@150.136.235.189:/tmp/
scp scripts/create_admin_user.py ubuntu@150.136.235.189:/tmp/

# Move to correct locations
sudo cp /tmp/localhost_only_flask.py /home/dataguardian/TwelvelabsWithOracleVector/src/
sudo cp /tmp/auth_utils.py /home/dataguardian/TwelvelabsWithOracleVector/twelvelabvideoai/src/
sudo cp /tmp/login.html /home/dataguardian/TwelvelabsWithOracleVector/twelvelabvideoai/src/templates/
sudo cp /tmp/index.html /home/dataguardian/TwelvelabsWithOracleVector/twelvelabvideoai/src/templates/
sudo cp /tmp/create_admin_user.py /home/dataguardian/TwelvelabsWithOracleVector/scripts/

# Set permissions
sudo chown -R dataguardian:dataguardian /home/dataguardian/TwelvelabsWithOracleVector

# Restart service
sudo systemctl restart dataguardian
```

### Step 4: Create Admin User
```bash
cd /home/dataguardian/TwelvelabsWithOracleVector
source twelvelabvideoai/bin/activate
python scripts/create_admin_user.py
```

### Step 5: Test Authentication
1. Navigate to http://150.136.235.189/
2. Should redirect to http://150.136.235.189/login
3. Login with admin credentials
4. Should redirect to main app
5. Test logout functionality

## Security Features Implemented

✅ Password hashing with bcrypt  
✅ Session-based authentication  
✅ Remember me functionality (30 days)  
✅ Login attempt logging  
✅ Role-based access control (admin, editor, viewer)  
✅ Protected routes with @login_required  
✅ Secure session cookies (HTTPOnly, SameSite)  
✅ User profile API endpoint  
✅ Beautiful login UI with gradient background  

## Default User Roles

- **admin**: Full access (upload, delete, creative tools, admin functions)
- **editor**: Can search, use tools, upload (cannot delete)
- **viewer**: Read-only access (search and view only)

## Environment Variables

Add to `.env` file:
```
FLASK_SECRET_KEY=<generate-random-32-char-string>
```

Generate secret key:
```python
import secrets
print(secrets.token_hex(32))
```

## Troubleshooting

### Issue: "Import bcrypt could not be resolved"
Solution: `pip install bcrypt`

### Issue: "users table does not exist"
Solution: Run create_users_table.sql in Oracle DB

### Issue: "No module named 'auth_utils'"
Solution: Verify auth_utils.py is in twelvelabvideoai/src/

### Issue: Login redirects to /login infinitely
Solution: Check that Flask-Login is initialized and user_loader is defined

