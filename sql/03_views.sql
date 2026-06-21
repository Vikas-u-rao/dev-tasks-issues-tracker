CREATE OR REPLACE VIEW v_workload_summary AS
SELECT u.id, u.username, u.role,
       COUNT(t.id) AS total_tickets,
       COUNT(t.id) FILTER (WHERE t.status != 'closed' AND t.status != 'resolved') AS active_tickets
FROM users u
LEFT JOIN tickets t ON u.id = t.assignee_id
GROUP BY u.id, u.username, u.role;

CREATE OR REPLACE VIEW v_overdue_tickets AS
SELECT * FROM tickets
WHERE due_date < CURRENT_DATE AND status NOT IN ('resolved', 'closed');
