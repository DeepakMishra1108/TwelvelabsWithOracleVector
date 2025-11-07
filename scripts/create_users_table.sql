-- Create Users Table for Authentication
-- Run this script in your Oracle Autonomous Database (TELCOVIDEOENCODE schema)

create table users (
   id            number generated always as identity primary key,
   username      varchar2(50) not null unique,
   password_hash varchar2(255) not null,
   email         varchar2(100),
   role          varchar2(20) default 'viewer' not null,
   is_active     number(1) default 1 not null,
   created_at    timestamp default current_timestamp,
   last_login    timestamp,
   constraint chk_role
      check ( role in ( 'admin',
                        'editor',
                        'viewer' ) ),
   constraint chk_is_active check ( is_active in ( 0,
                                                   1 ) )
);

-- Create index on username for faster lookups
create index idx_users_username on
   users (
      username
   );

-- Create audit log table for login attempts
create table login_attempts (
   id           number generated always as identity primary key,
   username     varchar2(50) not null,
   ip_address   varchar2(45),
   success      number(1) not null,
   attempt_time timestamp default current_timestamp,
   constraint chk_success check ( success in ( 0,
                                               1 ) )
);

-- Create index for recent login attempts lookup
create index idx_login_attempts_user_time on
   login_attempts (
      username,
      attempt_time
   );

-- Comments for documentation
comment on table users is
   'User authentication and authorization table';
comment on column users.role is
   'User role: admin (full access), editor (can modify), viewer (read-only)';
comment on column users.is_active is
   'Account status: 1 = active, 0 = disabled';
comment on table login_attempts is
   'Audit log for authentication attempts';

-- Grant privileges (adjust schema name if needed)
-- GRANT SELECT, INSERT, UPDATE ON users TO your_app_user;
-- GRANT SELECT, INSERT ON login_attempts TO your_app_user;

commit;