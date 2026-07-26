BEGIN;

CREATE TABLE IF NOT EXISTS public.guardrail_policies (
    guardrail_policy_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    policy_name text NOT NULL,
    policy_version integer NOT NULL CHECK (policy_version > 0),
    is_active boolean NOT NULL DEFAULT false,
    policy_config jsonb NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(policy_config) = 'object'),
    created_by uuid REFERENCES public.support_users(user_id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    activated_at timestamptz,
    UNIQUE (policy_name, policy_version)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_guardrail_policies_one_active
    ON public.guardrail_policies (policy_name)
    WHERE is_active;

CREATE TABLE IF NOT EXISTS public.guardrail_events (
    guardrail_event_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id uuid NOT NULL
        REFERENCES public.pipeline_runs(run_id) ON DELETE CASCADE,
    message_id uuid
        REFERENCES public.messages(message_id) ON DELETE CASCADE,
    guardrail_policy_id uuid
        REFERENCES public.guardrail_policies(guardrail_policy_id) ON DELETE SET NULL,
    guardrail_stage text NOT NULL
        CHECK (guardrail_stage IN ('input', 'retrieval', 'output')),
    check_type text NOT NULL,
    check_result text NOT NULL
        CHECK (check_result IN ('pass', 'block', 'review', 'error')),
    severity text NOT NULL DEFAULT 'info'
        CHECK (severity IN ('info', 'low', 'medium', 'high', 'critical')),
    reason_code text,
    details_safe jsonb NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(details_safe) = 'object'),
    check_latency_ms integer
        CHECK (check_latency_ms IS NULL OR check_latency_ms >= 0),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_guardrail_events_run_stage
    ON public.guardrail_events (run_id, guardrail_stage, created_at);
CREATE INDEX IF NOT EXISTS idx_guardrail_events_result_severity
    ON public.guardrail_events (check_result, severity, created_at DESC);

CREATE TABLE IF NOT EXISTS public.pii_detections (
    pii_detection_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    guardrail_event_id uuid NOT NULL
        REFERENCES public.guardrail_events(guardrail_event_id) ON DELETE CASCADE,
    pii_type text NOT NULL,
    replacement_token text NOT NULL,
    character_start integer CHECK (character_start IS NULL OR character_start >= 0),
    character_end integer CHECK (character_end IS NULL OR character_end >= 0),
    detector_name text NOT NULL,
    detector_version text,
    confidence numeric(7,6)
        CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (
        character_start IS NULL
        OR character_end IS NULL
        OR character_end >= character_start
    )
);

CREATE INDEX IF NOT EXISTS idx_pii_detections_type_created
    ON public.pii_detections (pii_type, created_at DESC);

CREATE TABLE IF NOT EXISTS public.escalation_cases (
    escalation_case_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id uuid NOT NULL
        REFERENCES public.conversations(conversation_id) ON DELETE CASCADE,
    source_message_id uuid NOT NULL
        REFERENCES public.messages(message_id) ON DELETE RESTRICT,
    run_id uuid
        REFERENCES public.pipeline_runs(run_id) ON DELETE SET NULL,
    reason_code text NOT NULL,
    severity text NOT NULL
        CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    case_status text NOT NULL DEFAULT 'open'
        CHECK (case_status IN (
            'open', 'assigned', 'in_review', 'waiting_customer',
            'resolved', 'closed'
        )),
    summary_safe text NOT NULL,
    intent_code text,
    intent_confidence numeric(7,6)
        CHECK (intent_confidence IS NULL OR intent_confidence BETWEEN 0 AND 1),
    assigned_agent_id uuid
        REFERENCES public.support_users(user_id) ON DELETE SET NULL,
    priority_score integer
        CHECK (priority_score IS NULL OR priority_score BETWEEN 0 AND 100),
    resolution_code text,
    metadata_safe jsonb NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(metadata_safe) = 'object'),
    created_at timestamptz NOT NULL DEFAULT now(),
    acknowledged_at timestamptz,
    resolved_at timestamptz,
    closed_at timestamptz,
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (source_message_id),
    CHECK (resolved_at IS NULL OR resolved_at >= created_at),
    CHECK (closed_at IS NULL OR closed_at >= created_at)
);

CREATE INDEX IF NOT EXISTS idx_escalation_cases_queue
    ON public.escalation_cases (case_status, severity, created_at);
CREATE INDEX IF NOT EXISTS idx_escalation_cases_agent_status
    ON public.escalation_cases (assigned_agent_id, case_status, updated_at DESC)
    WHERE assigned_agent_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_escalation_cases_conversation
    ON public.escalation_cases (conversation_id, created_at DESC);

DROP TRIGGER IF EXISTS trg_escalation_cases_updated_at
    ON public.escalation_cases;
CREATE TRIGGER trg_escalation_cases_updated_at
BEFORE UPDATE ON public.escalation_cases
FOR EACH ROW EXECUTE FUNCTION public.pi1_set_updated_at();

CREATE TABLE IF NOT EXISTS public.escalation_events (
    escalation_event_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    escalation_case_id uuid NOT NULL
        REFERENCES public.escalation_cases(escalation_case_id) ON DELETE CASCADE,
    actor_user_id uuid
        REFERENCES public.support_users(user_id) ON DELETE SET NULL,
    event_type text NOT NULL
        CHECK (event_type IN (
            'created', 'assigned', 'status_changed', 'note_added',
            'acknowledged', 'resolved', 'closed', 'reopened'
        )),
    from_status text,
    to_status text,
    note_safe text,
    event_metadata_safe jsonb NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(event_metadata_safe) = 'object'),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_escalation_events_case_created
    ON public.escalation_events (escalation_case_id, created_at);
CREATE INDEX IF NOT EXISTS idx_escalation_events_actor_created
    ON public.escalation_events (actor_user_id, created_at DESC)
    WHERE actor_user_id IS NOT NULL;

COMMIT;

