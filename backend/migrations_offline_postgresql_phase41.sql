BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 3bbfdbd42a4c

CREATE TABLE users (
    id UUID NOT NULL,
    name VARCHAR(200) NOT NULL,
    email VARCHAR(320) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL,
    is_active BOOLEAN NOT NULL,
    deactivated_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT ck_users_role CHECK (role IN ('participant', 'instructor', 'coordinator'))
);

CREATE UNIQUE INDEX ix_users_email ON users (email);

CREATE TABLE locations (
    id UUID NOT NULL,
    name VARCHAR(200) NOT NULL,
    address VARCHAR(300),
    reference VARCHAR(300),
    map_url VARCHAR(500),
    notes TEXT,
    is_active BOOLEAN NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    UNIQUE (name)
);

CREATE TABLE weekly_cycles (
    id UUID NOT NULL,
    week_start DATE NOT NULL,
    phase VARCHAR(40) NOT NULL,
    availability_deadline_note VARCHAR(200),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    UNIQUE (week_start),
    CONSTRAINT ck_weekly_cycles_phase CHECK (phase IN ('collecting_availability', 'enrollment_pending', 'enrollment_open', 'in_progress', 'closed'))
);

CREATE TABLE auth_sessions (
    id UUID NOT NULL,
    user_id UUID NOT NULL,
    token_hash VARCHAR(64) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    revoked_at TIMESTAMP WITH TIME ZONE,
    PRIMARY KEY (id),
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE,
    UNIQUE (token_hash),
    CONSTRAINT ck_auth_sessions_expiry CHECK (expires_at > created_at)
);

CREATE INDEX ix_auth_sessions_user_id ON auth_sessions (user_id);

CREATE UNIQUE INDEX ix_auth_sessions_token_hash ON auth_sessions (token_hash);

CREATE TABLE reiki_sessions (
    id UUID NOT NULL,
    cycle_id UUID,
    location_id UUID NOT NULL,
    instructor_id UUID,
    starts_at TIMESTAMP WITH TIME ZONE NOT NULL,
    ends_at TIMESTAMP WITH TIME ZONE NOT NULL,
    capacity INTEGER,
    status VARCHAR(20) NOT NULL,
    is_extra BOOLEAN NOT NULL,
    created_by UUID,
    cancelled_at TIMESTAMP WITH TIME ZONE,
    cancel_reason VARCHAR(500),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(cycle_id) REFERENCES weekly_cycles (id) ON DELETE SET NULL,
    FOREIGN KEY(instructor_id) REFERENCES users (id),
    FOREIGN KEY(location_id) REFERENCES locations (id),
    CONSTRAINT ck_reiki_sessions_period CHECK (ends_at > starts_at),
    CONSTRAINT ck_reiki_sessions_status CHECK (status IN ('scheduled', 'open', 'full', 'cancelled', 'needs_cover', 'uncovered', 'completed'))
);

CREATE INDEX ix_reiki_sessions_cycle_id ON reiki_sessions (cycle_id);

CREATE INDEX ix_reiki_sessions_instructor_id ON reiki_sessions (instructor_id);

CREATE INDEX ix_reiki_sessions_location_id ON reiki_sessions (location_id);

INSERT INTO alembic_version (version_num) VALUES ('3bbfdbd42a4c') RETURNING alembic_version.version_num;

-- Running upgrade 3bbfdbd42a4c -> a7c3d9e1f2b4

CREATE TABLE weekly_availabilities (
    id UUID NOT NULL,
    cycle_id UUID NOT NULL,
    instructor_id UUID NOT NULL,
    status VARCHAR(20) NOT NULL,
    submitted_at TIMESTAMP WITH TIME ZONE NOT NULL,
    note VARCHAR(500),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT fk_weekly_availabilities_cycle_id FOREIGN KEY(cycle_id) REFERENCES weekly_cycles (id) ON DELETE CASCADE,
    CONSTRAINT fk_weekly_availabilities_instructor_id FOREIGN KEY(instructor_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT uq_avail_cycle_instructor UNIQUE (cycle_id, instructor_id),
    CONSTRAINT ck_weekly_availabilities_status CHECK (status IN ('pending', 'submitted', 'unavailable'))
);

CREATE INDEX ix_weekly_availabilities_cycle_id ON weekly_availabilities (cycle_id);

CREATE INDEX ix_weekly_availabilities_instructor_id ON weekly_availabilities (instructor_id);

CREATE TABLE availability_entries (
    id UUID NOT NULL,
    availability_id UUID NOT NULL,
    kind VARCHAR(20) NOT NULL,
    starts_at TIMESTAMP WITH TIME ZONE NOT NULL,
    ends_at TIMESTAMP WITH TIME ZONE NOT NULL,
    location_id UUID,
    note VARCHAR(200),
    PRIMARY KEY (id),
    CONSTRAINT fk_availability_entries_availability_id FOREIGN KEY(availability_id) REFERENCES weekly_availabilities (id) ON DELETE CASCADE,
    CONSTRAINT fk_availability_entries_location_id FOREIGN KEY(location_id) REFERENCES locations (id) ON DELETE SET NULL,
    CONSTRAINT ck_avail_entry_period CHECK (ends_at > starts_at),
    CONSTRAINT ck_availability_entries_kind CHECK (kind IN ('available', 'unavailable'))
);

CREATE INDEX ix_availability_entries_availability_id ON availability_entries (availability_id);

CREATE INDEX ix_availability_entries_location_id ON availability_entries (location_id);

CREATE TABLE enrollments (
    id UUID NOT NULL,
    session_id UUID NOT NULL,
    participant_id UUID NOT NULL,
    status VARCHAR(20) NOT NULL,
    waitlist_position INTEGER,
    cancelled_at TIMESTAMP WITH TIME ZONE,
    cancel_reason VARCHAR(500),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT fk_enrollments_session_id FOREIGN KEY(session_id) REFERENCES reiki_sessions (id) ON DELETE CASCADE,
    CONSTRAINT fk_enrollments_participant_id FOREIGN KEY(participant_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT ck_enrollments_status CHECK (status IN ('confirmed', 'waitlisted', 'attended', 'cancelled')),
    CONSTRAINT ck_enrollments_waitlist_position CHECK (status != 'waitlisted' OR waitlist_position IS NOT NULL)
);

CREATE UNIQUE INDEX uq_enrollments_session_participant_active ON enrollments (session_id, participant_id) WHERE status IN ('confirmed', 'waitlisted', 'attended');

CREATE INDEX ix_enrollments_session_id ON enrollments (session_id);

CREATE INDEX ix_enrollments_participant_id ON enrollments (participant_id);

UPDATE alembic_version SET version_num='a7c3d9e1f2b4' WHERE alembic_version.version_num = '3bbfdbd42a4c';

-- Running upgrade a7c3d9e1f2b4 -> b8d4e2f6a9c1

CREATE TABLE cover_requests (
    id UUID NOT NULL,
    session_id UUID NOT NULL,
    original_instructor_id UUID,
    reason VARCHAR(500),
    status VARCHAR(20) NOT NULL,
    previous_session_status VARCHAR(20) NOT NULL,
    covered_by UUID,
    resolved_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT fk_cover_requests_session_id FOREIGN KEY(session_id) REFERENCES reiki_sessions (id) ON DELETE CASCADE,
    CONSTRAINT fk_cover_requests_covered_by FOREIGN KEY(covered_by) REFERENCES users (id) ON DELETE SET NULL,
    CONSTRAINT ck_cover_requests_status CHECK (status IN ('open', 'covered', 'uncovered')),
    CONSTRAINT uq_cover_requests_session UNIQUE (session_id)
);

CREATE INDEX ix_cover_requests_session_id ON cover_requests (session_id);

CREATE TABLE cover_invites (
    id UUID NOT NULL,
    request_id UUID NOT NULL,
    invited_instructor_id UUID NOT NULL,
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    accepted_at TIMESTAMP WITH TIME ZONE,
    declined_at TIMESTAMP WITH TIME ZONE,
    resolved_at TIMESTAMP WITH TIME ZONE,
    PRIMARY KEY (id),
    CONSTRAINT fk_cover_invites_request_id FOREIGN KEY(request_id) REFERENCES cover_requests (id) ON DELETE CASCADE,
    CONSTRAINT fk_cover_invites_invited_instructor_id FOREIGN KEY(invited_instructor_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT ck_cover_invites_status CHECK (status IN ('pending', 'accepted', 'taken', 'declined', 'expired', 'withdrawn')),
    CONSTRAINT uq_cover_invite_req_instructor UNIQUE (request_id, invited_instructor_id)
);

CREATE INDEX ix_cover_invites_request_id ON cover_invites (request_id);

CREATE INDEX ix_cover_invites_invited_instructor_id ON cover_invites (invited_instructor_id);

CREATE INDEX ix_cover_invites_instructor_status ON cover_invites (invited_instructor_id, status);

UPDATE alembic_version SET version_num='b8d4e2f6a9c1' WHERE alembic_version.version_num = 'a7c3d9e1f2b4';

-- Running upgrade b8d4e2f6a9c1 -> c4f5a6b7d8e9

ALTER TABLE enrollments ADD COLUMN reallocation_id UUID;

CREATE INDEX ix_enrollments_reallocation_id ON enrollments (reallocation_id);

CREATE TABLE reallocation_cases (
    id UUID NOT NULL,
    origin_session_id UUID NOT NULL,
    origin_enrollment_id UUID NOT NULL,
    participant_id UUID NOT NULL,
    status VARCHAR(20) NOT NULL,
    alternative VARCHAR(30),
    target_session_id UUID,
    priority_granted_at TIMESTAMP WITH TIME ZONE,
    decided_at TIMESTAMP WITH TIME ZONE,
    decided_by UUID,
    dismissal_reason VARCHAR(500),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(origin_session_id) REFERENCES reiki_sessions (id) ON DELETE CASCADE,
    FOREIGN KEY(origin_enrollment_id) REFERENCES enrollments (id) ON DELETE CASCADE,
    FOREIGN KEY(participant_id) REFERENCES users (id) ON DELETE CASCADE,
    FOREIGN KEY(target_session_id) REFERENCES reiki_sessions (id) ON DELETE SET NULL,
    FOREIGN KEY(decided_by) REFERENCES users (id) ON DELETE SET NULL,
    CONSTRAINT uq_reallocation_origin_enrollment UNIQUE (origin_enrollment_id),
    CONSTRAINT ck_reallocation_status CHECK (status IN ('pending', 'applied', 'dismissed')),
    CONSTRAINT ck_reallocation_alternative CHECK (alternative IS NULL OR alternative IN ('extra_session', 'future_priority'))
);

CREATE INDEX ix_reallocation_cases_origin_session_id ON reallocation_cases (origin_session_id);

CREATE INDEX ix_reallocation_cases_origin_enrollment_id ON reallocation_cases (origin_enrollment_id);

CREATE INDEX ix_reallocation_cases_participant_id ON reallocation_cases (participant_id);

CREATE INDEX ix_reallocation_cases_target_session_id ON reallocation_cases (target_session_id);

CREATE TABLE reallocation_history (
    id UUID NOT NULL,
    case_id UUID NOT NULL,
    action VARCHAR(30) NOT NULL,
    detail VARCHAR(500),
    actor_id UUID,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(case_id) REFERENCES reallocation_cases (id) ON DELETE CASCADE,
    FOREIGN KEY(actor_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_reallocation_history_case_id ON reallocation_history (case_id);

UPDATE alembic_version SET version_num='c4f5a6b7d8e9' WHERE alembic_version.version_num = 'b8d4e2f6a9c1';

-- Running upgrade c4f5a6b7d8e9 -> d5e6f7a8b9c0

ALTER TABLE enrollments ADD CONSTRAINT fk_enrollments_reallocation_id FOREIGN KEY(reallocation_id) REFERENCES reallocation_cases (id) ON DELETE RESTRICT;

CREATE TABLE notifications (
    id UUID NOT NULL,
    recipient_id UUID NOT NULL,
    kind VARCHAR(40) NOT NULL,
    title VARCHAR(200) NOT NULL,
    message VARCHAR(1000) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    read_at TIMESTAMP WITH TIME ZONE,
    session_id UUID,
    PRIMARY KEY (id),
    FOREIGN KEY(recipient_id) REFERENCES users (id) ON DELETE CASCADE,
    FOREIGN KEY(session_id) REFERENCES reiki_sessions (id) ON DELETE SET NULL
);

CREATE INDEX ix_notifications_recipient_id ON notifications (recipient_id);

CREATE INDEX ix_notifications_session_id ON notifications (session_id);

CREATE TABLE audit_events (
    id UUID NOT NULL,
    kind VARCHAR(40) NOT NULL,
    description VARCHAR(1000) NOT NULL,
    actor_id UUID,
    session_id UUID,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(actor_id) REFERENCES users (id) ON DELETE SET NULL,
    FOREIGN KEY(session_id) REFERENCES reiki_sessions (id) ON DELETE SET NULL
);

CREATE INDEX ix_audit_events_kind ON audit_events (kind);

CREATE INDEX ix_audit_events_actor_id ON audit_events (actor_id);

CREATE INDEX ix_audit_events_session_id ON audit_events (session_id);

UPDATE alembic_version SET version_num='d5e6f7a8b9c0' WHERE alembic_version.version_num = 'c4f5a6b7d8e9';

COMMIT;
