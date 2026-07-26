BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;

CREATE OR REPLACE FUNCTION public.pi1_set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

CREATE TABLE IF NOT EXISTS public.support_users (
    user_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    external_subject text UNIQUE,
    email_hash text,
    display_name text,
    user_role text NOT NULL DEFAULT 'customer'
        CHECK (user_role IN ('customer', 'agent', 'admin', 'auditor')),
    user_status text NOT NULL DEFAULT 'active'
        CHECK (user_status IN ('pending', 'active', 'disabled', 'deleted')),
    preferences jsonb NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(preferences) = 'object'),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    last_login_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_support_users_role_status
    ON public.support_users (user_role, user_status);

DROP TRIGGER IF EXISTS trg_support_users_updated_at
    ON public.support_users;
CREATE TRIGGER trg_support_users_updated_at
BEFORE UPDATE ON public.support_users
FOR EACH ROW EXECUTE FUNCTION public.pi1_set_updated_at();

CREATE TABLE IF NOT EXISTS public.conversations (
    conversation_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_user_id uuid REFERENCES public.support_users(user_id)
        ON DELETE SET NULL,
    assigned_agent_id uuid REFERENCES public.support_users(user_id)
        ON DELETE SET NULL,
    channel text NOT NULL DEFAULT 'api'
        CHECK (channel IN ('api', 'web', 'mobile', 'email', 'internal')),
    conversation_status text NOT NULL DEFAULT 'open'
        CHECK (conversation_status IN (
            'open', 'waiting_customer', 'waiting_agent', 'escalated',
            'resolved', 'closed'
        )),
    last_intent text,
    locale text NOT NULL DEFAULT 'en-US',
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(metadata) = 'object'),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    last_message_at timestamptz,
    closed_at timestamptz,
    CHECK (
        (conversation_status = 'closed' AND closed_at IS NOT NULL)
        OR conversation_status <> 'closed'
    )
);

CREATE INDEX IF NOT EXISTS idx_conversations_customer_created
    ON public.conversations (customer_user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_conversations_status_updated
    ON public.conversations (conversation_status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_conversations_agent_status
    ON public.conversations (assigned_agent_id, conversation_status)
    WHERE assigned_agent_id IS NOT NULL;

DROP TRIGGER IF EXISTS trg_conversations_updated_at
    ON public.conversations;
CREATE TRIGGER trg_conversations_updated_at
BEFORE UPDATE ON public.conversations
FOR EACH ROW EXECUTE FUNCTION public.pi1_set_updated_at();

CREATE TABLE IF NOT EXISTS public.messages (
    message_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id uuid NOT NULL
        REFERENCES public.conversations(conversation_id) ON DELETE CASCADE,
    sender_user_id uuid REFERENCES public.support_users(user_id)
        ON DELETE SET NULL,
    parent_message_id uuid REFERENCES public.messages(message_id)
        ON DELETE SET NULL,
    message_role text NOT NULL
        CHECK (message_role IN ('customer', 'assistant', 'agent', 'system', 'tool')),
    content_redacted text NOT NULL
        CHECK (length(btrim(content_redacted)) > 0),
    content_encrypted bytea,
    content_sha256 text,
    model_name text,
    prompt_version text,
    input_tokens integer CHECK (input_tokens IS NULL OR input_tokens >= 0),
    output_tokens integer CHECK (output_tokens IS NULL OR output_tokens >= 0),
    message_status text NOT NULL DEFAULT 'stored'
        CHECK (message_status IN ('received', 'processing', 'stored', 'blocked', 'failed')),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(metadata) = 'object'),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation_created
    ON public.messages (conversation_id, created_at, message_id);
CREATE INDEX IF NOT EXISTS idx_messages_sender_created
    ON public.messages (sender_user_id, created_at DESC)
    WHERE sender_user_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_messages_status
    ON public.messages (message_status, created_at DESC);

CREATE TABLE IF NOT EXISTS public.pipeline_runs (
    run_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    trace_id uuid NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    conversation_id uuid NOT NULL
        REFERENCES public.conversations(conversation_id) ON DELETE CASCADE,
    customer_message_id uuid NOT NULL
        REFERENCES public.messages(message_id) ON DELETE CASCADE,
    assistant_message_id uuid
        REFERENCES public.messages(message_id) ON DELETE SET NULL,
    run_status text NOT NULL DEFAULT 'started'
        CHECK (run_status IN ('started', 'completed', 'escalated', 'failed')),
    final_outcome text
        CHECK (final_outcome IS NULL OR final_outcome IN (
            'answered', 'clarified', 'escalated', 'blocked', 'failed'
        )),
    selected_route text,
    error_code text,
    error_detail_safe text,
    total_latency_ms integer
        CHECK (total_latency_ms IS NULL OR total_latency_ms >= 0),
    started_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    CHECK (
        (run_status = 'started' AND completed_at IS NULL)
        OR (run_status <> 'started' AND completed_at IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_conversation_started
    ON public.pipeline_runs (conversation_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status_started
    ON public.pipeline_runs (run_status, started_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS uq_pipeline_runs_customer_message
    ON public.pipeline_runs (customer_message_id);

CREATE TABLE IF NOT EXISTS public.idempotency_records (
    idempotency_record_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    idempotency_key text NOT NULL,
    user_id uuid NOT NULL
        REFERENCES public.support_users(user_id) ON DELETE CASCADE,
    request_path text NOT NULL,
    request_hash text NOT NULL,
    record_status text NOT NULL DEFAULT 'processing'
        CHECK (record_status IN ('processing', 'completed', 'failed')),
    response_status_code integer
        CHECK (response_status_code IS NULL OR response_status_code BETWEEN 100 AND 599),
    response_body jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    UNIQUE (user_id, request_path, idempotency_key),
    CHECK (expires_at > created_at)
);

CREATE INDEX IF NOT EXISTS idx_idempotency_records_expires
    ON public.idempotency_records (expires_at);

COMMIT;
