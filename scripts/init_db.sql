-- ============================================
-- HR Helpdesk Database Schema & Seed Data
-- ============================================

-- Create database (run as superuser first)
-- CREATE DATABASE helpdesk;
-- CREATE USER helpdesk_user WITH PASSWORD 'helpdesk_pass';
-- GRANT ALL PRIVILEGES ON DATABASE helpdesk TO helpdesk_user;

-- Connect to helpdesk db then run below:

-- Employees table
CREATE TABLE IF NOT EXISTS employees (
    employee_id   VARCHAR(10) PRIMARY KEY,
    full_name     VARCHAR(100) NOT NULL,
    email         VARCHAR(100) UNIQUE NOT NULL,
    department    VARCHAR(50) NOT NULL,
    designation   VARCHAR(100) NOT NULL,
    date_joined   DATE NOT NULL,
    manager_id    VARCHAR(10) REFERENCES employees(employee_id),
    is_active     BOOLEAN DEFAULT TRUE
);

-- Leave balances table
CREATE TABLE IF NOT EXISTS leave_balances (
    id              SERIAL PRIMARY KEY,
    employee_id     VARCHAR(10) REFERENCES employees(employee_id),
    leave_type      VARCHAR(30) NOT NULL,   -- 'annual', 'sick', 'casual', 'maternity', 'paternity'
    total_days      INTEGER NOT NULL,
    used_days       INTEGER DEFAULT 0,
    year            INTEGER NOT NULL DEFAULT EXTRACT(YEAR FROM CURRENT_DATE),
    UNIQUE (employee_id, leave_type, year)
);

-- Leave requests table
CREATE TABLE IF NOT EXISTS leave_requests (
    id              SERIAL PRIMARY KEY,
    employee_id     VARCHAR(10) REFERENCES employees(employee_id),
    leave_type      VARCHAR(30) NOT NULL,
    start_date      DATE NOT NULL,
    end_date        DATE NOT NULL,
    days_requested  INTEGER NOT NULL,
    status          VARCHAR(20) DEFAULT 'pending',  -- 'pending','approved','rejected'
    reason          TEXT,
    applied_at      TIMESTAMP DEFAULT NOW()
);

-- IT assets table
CREATE TABLE IF NOT EXISTS it_assets (
    id              SERIAL PRIMARY KEY,
    asset_tag       VARCHAR(20) UNIQUE NOT NULL,
    asset_type      VARCHAR(50) NOT NULL,   -- 'laptop','monitor','phone','keyboard'
    brand           VARCHAR(50),
    model           VARCHAR(100),
    serial_number   VARCHAR(100),
    assigned_to     VARCHAR(10) REFERENCES employees(employee_id),
    assigned_date   DATE,
    status          VARCHAR(20) DEFAULT 'in_use'  -- 'in_use','available','retired'
);

-- IT tickets table
CREATE TABLE IF NOT EXISTS it_tickets (
    id              SERIAL PRIMARY KEY,
    ticket_id       VARCHAR(15) UNIQUE NOT NULL,
    employee_id     VARCHAR(10) REFERENCES employees(employee_id),
    category        VARCHAR(50) NOT NULL,   -- 'hardware','software','access','network','other'
    subject         VARCHAR(200) NOT NULL,
    description     TEXT,
    priority        VARCHAR(10) DEFAULT 'medium',  -- 'low','medium','high','critical'
    status          VARCHAR(20) DEFAULT 'open',    -- 'open','in_progress','resolved','closed'
    created_at      TIMESTAMP DEFAULT NOW(),
    resolved_at     TIMESTAMP
);

-- ============================================
-- Seed Data
-- ============================================

INSERT INTO employees (employee_id, full_name, email, department, designation, date_joined) VALUES
('E101', 'Priya Sharma',    'priya.sharma@company.com',    'Engineering',  'Senior Software Engineer',  '2021-03-15'),
('E102', 'Rahul Verma',     'rahul.verma@company.com',     'Engineering',  'Software Engineer',         '2022-07-01'),
('E103', 'Anjali Singh',    'anjali.singh@company.com',    'HR',           'HR Manager',                '2020-01-10'),
('E104', 'Karan Mehta',     'karan.mehta@company.com',     'Finance',      'Financial Analyst',         '2023-02-20'),
('E105', 'Sneha Patel',     'sneha.patel@company.com',     'Marketing',    'Marketing Lead',            '2021-09-05'),
('E106', 'Arjun Nair',      'arjun.nair@company.com',      'Engineering',  'DevOps Engineer',           '2022-11-14'),
('E107', 'Meera Joshi',     'meera.joshi@company.com',     'Design',       'UX Designer',               '2023-05-01'),
('E108', 'Vikram Rathi',    'vikram.rathi@company.com',    'Sales',        'Sales Manager',             '2019-08-20'),
('E109', 'Pooja Gupta',     'pooja.gupta@company.com',     'Engineering',  'QA Engineer',               '2022-04-11'),
('E110', 'Rohit Das',       'rohit.das@company.com',       'IT',           'IT Support Engineer',       '2021-06-30')
ON CONFLICT (employee_id) DO NOTHING;

-- Update manager relationships
UPDATE employees SET manager_id = 'E101' WHERE employee_id IN ('E102', 'E106', 'E109');
UPDATE employees SET manager_id = 'E103' WHERE employee_id IN ('E104', 'E105');

-- Leave balances (2026)
INSERT INTO leave_balances (employee_id, leave_type, total_days, used_days, year) VALUES
('E101', 'annual',   18, 5,  2026),
('E101', 'sick',     12, 2,  2026),
('E101', 'casual',   6,  1,  2026),
('E102', 'annual',   18, 10, 2026),
('E102', 'sick',     12, 4,  2026),
('E102', 'casual',   6,  2,  2026),
('E103', 'annual',   21, 3,  2026),
('E103', 'sick',     12, 0,  2026),
('E103', 'casual',   6,  2,  2026),
('E104', 'annual',   18, 7,  2026),
('E104', 'sick',     12, 1,  2026),
('E104', 'casual',   6,  0,  2026),
('E105', 'annual',   18, 12, 2026),
('E105', 'sick',     12, 6,  2026),
('E105', 'casual',   6,  3,  2026),
('E106', 'annual',   18, 2,  2026),
('E106', 'sick',     12, 0,  2026),
('E106', 'casual',   6,  1,  2026),
('E107', 'annual',   18, 8,  2026),
('E107', 'sick',     12, 3,  2026),
('E107', 'casual',   6,  2,  2026),
('E108', 'annual',   21, 15, 2026),
('E108', 'sick',     12, 5,  2026),
('E108', 'casual',   6,  4,  2026),
('E109', 'annual',   18, 4,  2026),
('E109', 'sick',     12, 2,  2026),
('E109', 'casual',   6,  1,  2026),
('E110', 'annual',   18, 6,  2026),
('E110', 'sick',     12, 3,  2026),
('E110', 'casual',   6,  0,  2026)
ON CONFLICT (employee_id, leave_type, year) DO NOTHING;

-- IT Assets
INSERT INTO it_assets (asset_tag, asset_type, brand, model, serial_number, assigned_to, assigned_date) VALUES
('ASSET-001', 'laptop',   'Apple',    'MacBook Pro 14"',  'C02ZK1234567', 'E101', '2021-04-01'),
('ASSET-002', 'laptop',   'Dell',     'XPS 15',           'DL789XYZ1234', 'E102', '2022-08-01'),
('ASSET-003', 'laptop',   'Lenovo',   'ThinkPad X1',      'LN456ABC7890', 'E103', '2020-02-01'),
('ASSET-004', 'monitor',  'LG',       '27UK850',          'LG27UK001234', 'E101', '2021-04-01'),
('ASSET-005', 'monitor',  'Dell',     'U2722D',           'DLU2722X9876', 'E102', '2022-08-01'),
('ASSET-006', 'phone',    'Apple',    'iPhone 15',        'IP15XY123456', 'E108', '2023-10-01'),
('ASSET-007', 'laptop',   'Apple',    'MacBook Air M2',   'C02ZM2345678', 'E107', '2023-06-01'),
('ASSET-008', 'laptop',   'HP',       'EliteBook 840',    'HP840ZXC1234', 'E106', '2022-12-01')
ON CONFLICT (asset_tag) DO NOTHING;

-- IT Tickets
INSERT INTO it_tickets (ticket_id, employee_id, category, subject, description, priority, status, created_at, resolved_at) VALUES
('TKT-2026-001', 'E102', 'software', 'VPN not connecting',          'Unable to connect to company VPN from home.',              'high',     'resolved',     '2026-10-01 09:00:00', '2026-10-01 11:30:00'),
('TKT-2026-002', 'E104', 'access',   'Need access to Salesforce',   'Require read access to Salesforce for financial reports.',  'medium',   'in_progress',  '2026-11-10 10:00:00', NULL),
('TKT-2026-003', 'E107', 'hardware', 'Monitor flickering',          'External monitor flickers intermittently.',                'medium',   'open',         '2026-11-18 14:00:00', NULL),
('TKT-2026-004', 'E105', 'software', 'Slack notifications broken',  'Desktop notifications from Slack not appearing.',          'low',      'resolved',     '2026-11-05 11:00:00', '2026-11-05 15:00:00'),
('TKT-2026-005', 'E109', 'network',  'Slow WiFi at office',         'WiFi speed is very slow at desk 4B.',                     'medium',   'open',         '2026-11-19 09:30:00', NULL)
ON CONFLICT (ticket_id) DO NOTHING;
