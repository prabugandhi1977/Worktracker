-- Curated reporting views for Power BI (PRD section 17).
-- Power BI should connect to PostgreSQL and read from these views only,
-- never from rfid_events or the application's operational tables directly.
--
-- Apply with:
--   docker compose exec -T postgres psql -U worktrack -d worktrack < sql/reporting_views.sql

CREATE OR REPLACE VIEW vw_employee_daily_hours AS
SELECT
    a.employee_id,
    e.employee_code,
    e.name AS employee_name,
    e.department_id,
    a.work_date,
    a.gross_minutes / 60.0 AS gross_hours,
    a.break_minutes / 60.0 AS break_hours,
    a.net_minutes / 60.0 AS net_hours,
    a.overtime_minutes / 60.0 AS overtime_hours
FROM attendance a
JOIN employees e ON e.id = a.employee_id;

CREATE OR REPLACE VIEW vw_project_daily_hours AS
SELECT
    t.project_id,
    p.project_code,
    p.name AS project_name,
    DATE(t.start_time) AS work_date,
    SUM(t.duration_minutes) / 60.0 AS actual_hours
FROM time_logs t
JOIN projects p ON p.id = t.project_id
WHERE t.is_break = FALSE
GROUP BY t.project_id, p.project_code, p.name, DATE(t.start_time);

CREATE OR REPLACE VIEW vw_project_activity_hours AS
SELECT
    t.project_id,
    t.activity_id,
    act.name AS activity_name,
    act.category AS activity_category,
    SUM(t.duration_minutes) / 60.0 AS hours
FROM time_logs t
LEFT JOIN activities act ON act.id = t.activity_id
WHERE t.is_break = FALSE
GROUP BY t.project_id, t.activity_id, act.name, act.category;

CREATE OR REPLACE VIEW vw_department_utilization AS
SELECT
    e.department_id,
    a.work_date,
    COUNT(DISTINCT a.employee_id) AS employees_present,
    SUM(a.net_minutes) / 60.0 AS total_net_hours,
    SUM(a.overtime_minutes) / 60.0 AS total_overtime_hours
FROM attendance a
JOIN employees e ON e.id = a.employee_id
GROUP BY e.department_id, a.work_date;

CREATE OR REPLACE VIEW vw_attendance_daily AS
SELECT
    a.employee_id,
    a.work_date,
    a.first_entry,
    a.last_exit,
    CASE WHEN a.first_entry IS NULL THEN 'ABSENT'
         WHEN a.last_exit IS NULL THEN 'OPEN'
         ELSE 'COMPLETE' END AS attendance_state
FROM attendance a;

CREATE OR REPLACE VIEW vw_overtime AS
SELECT
    a.employee_id,
    e.department_id,
    a.work_date,
    a.overtime_minutes / 60.0 AS overtime_hours
FROM attendance a
JOIN employees e ON e.id = a.employee_id
WHERE a.overtime_minutes > 0;

CREATE OR REPLACE VIEW vw_project_planned_vs_actual AS
SELECT
    p.id AS project_id,
    p.project_code,
    p.name AS project_name,
    p.planned_hours,
    COALESCE(SUM(t.duration_minutes) / 60.0, 0) AS actual_hours,
    p.planned_hours - COALESCE(SUM(t.duration_minutes) / 60.0, 0) AS remaining_hours
FROM projects p
LEFT JOIN time_logs t ON t.project_id = p.id AND t.is_break = FALSE
GROUP BY p.id, p.project_code, p.name, p.planned_hours;

CREATE OR REPLACE VIEW vw_project_manpower_cost AS
SELECT
    t.project_id,
    p.project_code,
    SUM((t.duration_minutes / 60.0) * COALESCE(pa.hourly_cost_rate, 0)) AS actual_manpower_cost,
    p.budgeted_manpower_cost
FROM time_logs t
JOIN projects p ON p.id = t.project_id
LEFT JOIN project_assignments pa ON pa.project_id = t.project_id AND pa.employee_id = t.employee_id
WHERE t.is_break = FALSE
GROUP BY t.project_id, p.project_code, p.budgeted_manpower_cost;
