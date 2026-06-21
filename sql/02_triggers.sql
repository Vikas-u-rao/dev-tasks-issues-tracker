CREATE OR REPLACE FUNCTION fn_enforce_ticket_transition()
RETURNS TRIGGER AS $$
BEGIN
    -- Only check if status changed
    IF OLD.status IS DISTINCT FROM NEW.status THEN
        IF OLD.status = 'open' AND NEW.status = 'in_progress' AND NEW.assignee_id IS NULL THEN
            RAISE EXCEPTION 'A developer must be assigned to start progress.';
        ELSIF OLD.status = 'open' AND NEW.status = 'in_progress' THEN
            -- OK
        ELSIF OLD.status = 'in_progress' AND NEW.status IN ('in_review', 'open') THEN
            -- OK
        ELSIF OLD.status = 'in_review' AND NEW.status IN ('resolved', 'in_progress') THEN
            -- OK
        ELSIF OLD.status = 'resolved' AND NEW.status = 'closed' THEN
            -- OK
        ELSIF OLD.status = 'closed' AND NEW.status = 'open' THEN
            -- OK (Flask will check if current user is manager)
        ELSE
            RAISE EXCEPTION 'Invalid status transition from % to %', OLD.status, NEW.status;
        END IF;
    END IF;
    
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_ticket_transition ON tickets;
CREATE TRIGGER trg_ticket_transition
BEFORE UPDATE ON tickets
FOR EACH ROW
EXECUTE FUNCTION fn_enforce_ticket_transition();

CREATE OR REPLACE FUNCTION fn_log_status_change()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.status IS DISTINCT FROM NEW.status THEN
        INSERT INTO audit_logs (ticket_id, action, old_value, new_value)
        VALUES (NEW.id, 'status_change', OLD.status::text, NEW.status::text);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_log_status_change ON tickets;
CREATE TRIGGER trg_log_status_change
AFTER UPDATE ON tickets
FOR EACH ROW
EXECUTE FUNCTION fn_log_status_change();
