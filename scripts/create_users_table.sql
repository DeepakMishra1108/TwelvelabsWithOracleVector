-- Create Users Table for Authentication
-- Run this script in your Oracle Autonomous Database (TELCOVIDEOENCODE schema)

CREATE TABLE users (
    id NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username VARCHAR2(50) NOT NULL UNIQUE,
    password_hash VARCHAR2(255) NOT NULL,
    email VARCHAR2(100),
    role VARCHAR2(20) DEFAULT 'viewer' NOT NULL,
    is_active NUMBER(1) DEFAULT 1 NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    CONSTRAINT chk_role CHECK (role IN ('admin', 'editor', 'viewer')),
    CONSTRAINT chk_is_active CHECK (is_active IN (0, 1))
);

-- Create index on username for faster lookups
CREATE INDEX idx_users_username ON users(username);

-- Create audit log table for login attempts
CREATE TABLE login_attempts (
    id NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username VARCHAR2(50) NOT NULL,
    ip_address VARCHAR2(45),
    success NUMBER(1) NOT NULL,
    attempt_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_success CHECK (success IN (0, 1))
);

-- Create index for recent login attempts lookup
CREATE INDEX idx_login_attempts_user_time ON login_attempts(username, attempt_time);

-- Comments for documentation
COMMENT ON TABLE users IS 'User authentication and authorization table';
COMMENT ON COLUMN users.role IS 'User role: admin (full access), editor (can modify), viewer (read-only)';
COMMENT ON COLUMN users.is_active IS 'Account status: 1 = active, 0 = disabled';
COMMENT ON TABLE login_attempts IS 'Audit log for authentication attempts';

-- Grant privileges (adjust schema name if needed)
-- GRANT SELECT, INSERT, UPDATE ON users TO your_app_user;
-- GRANT SELECT, INSERT ON login_attempts TO your_app_user;

COMMIT;
