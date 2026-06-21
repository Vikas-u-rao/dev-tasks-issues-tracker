# Developer Software Issue & Task Tracker

A collaborative, database-first mini-project building a secure, role-based Issue Tracking System. 

---

## Technology Stack

| Layer | Technology |
|---|---|
| **Database** | PostgreSQL (Raw SQL, constraints, views, and database triggers) |
| **Backend** | Python + Flask & `psycopg2` (No ORM, raw queries only) |
| **Frontend** | Jinja2 Templates + Bootstrap 5 + Vanilla CSS & JS |
| **Auth** | Flask session cookies + `werkzeug.security` password hashing |

## Database Architecture & Relationships

```
                        ┌──────────────┐
                        │    users     │
                        └──────┬───────┘
                               │ 1
                               │
            ┌──────────────────┼─────────────────┐
            │ 1..*             │ 1..*            │ 1..*
    ┌───────▼───────┐   ┌──────▼───────┐   ┌─────▼────────┐
    │    tickets    ├───►   comments   │   │  audit_log   │
    └───────┬───────┘ 1 └──────────────┘   └──────────────┘
            │ 1
            │
    ┌───────▼───────┐
    │  ticket_tags  │
    └───────▲───────┘
            │ 1..*
            │
        ┌───┴───┐
        │ tags  │
        └───────┘
```

1. **`users`**: Contains account info, hashed passwords, and a role enum (`developer`, `manager`, `reporter`).
2. **`tickets`**: Stores the ticket details, links to its creator and assignee, and self-references a parent ticket.
3. **`tags`**: Unique categories (e.g. `bug`, `documentation`) mapped to tickets through the `ticket_tags` join table.
4. **`comments`**: Threaded textual logs belonging to a ticket and written by a user.
5. **`audit_log`**: System logs recording the historical status changes of each ticket.

---

## State Machine & Triggers

All ticket lifecycle transitions must be verified at the database level using a `BEFORE UPDATE` trigger on the `tickets` table.

```
       ┌──────────────┐
       │     open     │
       └──────┬───────┘
              │ (Must assign a developer first)
              ▼
       ┌──────────────┐
  ┌───►│ in_progress  │◄───┐
  │    └──────┬───────┘    │
  │           │            │
  │           ▼            │
  │    ┌──────────────┐    │
  │    │  in_review   │    │
  │    └──────┬───────┘    │
  │           │            │
  │           ▼            │
  │    ┌──────────────┐    │
  │    │   resolved   │    │
  │    └──────┬───────┘    │
  │           │            │
  │           ▼            │
  │    ┌──────────────┐    │
  │    │    closed    │    │
  │    └──────┬───────┘    │
  │           │            │
  └───────────┼────────────┘
              │ (Manager only)
              ▼
         [Reopened]
```

### Transition Constraints:
* `open` ➔ `in_progress` (Requires an assignee to be set)
* `in_progress` ➔ `in_review` or `open`
* `in_review` ➔ `resolved` or `in_progress`
* `resolved` ➔ `closed`
* `closed` ➔ `open` (Manager only)
* *All other transitions must be blocked and raise an exception.*

---

## Role-Based Access Control (RBAC)

These rules are enforced in route handlers before executing database operations:

| Action | Developer | Manager | Reporter |
|---|:---:|:---:|:---:|
| **Create Ticket** | ✓ | ✓ | ✓ |
| **Assign Ticket** | Self-assign only | Anyone | ✗ |
| **Update Status** | ✓ | ✓ | ✗ |
| **Close / Reopen** | ✗ | ✓ | ✗ |
| **Delete Ticket** | ✗ | ✓ | ✗ |

---

##  UI & Design Guidelines

### Status Badge Palette
* `open` ➔ `.bg-secondary` (Gray)
* `in_progress` ➔ `.bg-primary` (Blue)
* `in_review` ➔ `.bg-warning .text-dark` (Yellow)
* `resolved` ➔ `.bg-success` (Green)
* `closed` ➔ `.bg-dark` (Dark Gray)

### Priority Badge Palette
* `low` ➔ `.bg-secondary`
* `medium` ➔ `.bg-info .text-dark`
* `high` ➔ `.bg-warning .text-dark`
* `critical` ➔ `.bg-danger`

### Dashboard KPIs
1. **Total Open Tickets**
2. **Critical Tickets Not Yet Resolved**
3. **Tickets Resolved This Week**
4. **My Active Tickets** (Display to developers only)
