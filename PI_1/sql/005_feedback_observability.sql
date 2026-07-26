BEGIN;

CREATE TABLE IF NOT EXISTS public.feedback (
    feedback_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id uuid NOT NULL
        REFERENCES public.conversations(conversation_id) ON DELETE CASCADE,
    message_id uuid NOT NULL
        REFERENCES public.messages(message_id) ON DELETE CASCADE,
    submitted_by_user_id uuid
        REFERENCES public.support_users(user_id) ON DELETE SET NULL,
    submission_key text NOT NULL,
    rating text NOT NULL
        CHECK (rating IN ('positive', 'negative')),
    reason_code text,
    comment_redacted text,
    is_resolved boolean,
    feedback_status text NOT NULL DEFAULT 'active'
        CHECK (feedback_status IN ('active', 'superseded', 'removed')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_feedback_active_user_message
    ON public.feedback (message_id, submission_key)
    WHERE feedback_status = 'active';
CREATE INDEX IF NOT EXISTS idx_feedback_rating_created
    ON public.feedback (rating, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_feedback_conversation
    ON public.feedback (conversation_id, created_at DESC);

DROP TRIGGER IF EXISTS trg_feedback_updated_at
    ON public.feedback;
CREATE TRIGGER trg_feedback_updated_at
BEFORE UPDATE ON public.feedback
FOR EACH ROW EXECUTE FUNCTION public.pi1_set_updated_at();

CREATE TABLE IF NOT EXISTS public.application_events (
    application_event_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    trace_id uuid,
    run_id uuid
        REFERENCES public.pipeline_runs(run_id) ON DELETE SET NULL,
    conversation_id uuid
        REFERENCES public.conversations(conversation_id) ON DELETE SET NULL,
    message_id uuid
        REFERENCES public.messages(message_id) ON DELETE SET NULL,
    event_name text NOT NULL,
    event_category text NOT NULL
        CHECK (event_category IN (
            'api', 'nlu', 'routing', 'retrieval', 'generation',
            'guardrail', 'escalation', 'feedback', 'dependency', 'security'
        )),
    event_status text NOT NULL
        CHECK (event_status IN ('started', 'succeeded', 'failed', 'blocked')),
    duration_ms integer CHECK (duration_ms IS NULL OR duration_ms >= 0),
    model_name text,
    model_version text,
    prompt_version text,
    input_tokens integer CHECK (input_tokens IS NULL OR input_tokens >= 0),
    output_tokens integer CHECK (output_tokens IS NULL OR output_tokens >= 0),
    retry_count integer NOT NULL DEFAULT 0 CHECK (retry_count >= 0),
    error_code text,
    attributes_safe jsonb NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(attributes_safe) = 'object'),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_application_events_trace_created
    ON public.application_events (trace_id, created_at)
    WHERE trace_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_application_events_run_created
    ON public.application_events (run_id, created_at)
    WHERE run_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_application_events_category_status_created
    ON public.application_events (event_category, event_status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_application_events_name_created
    ON public.application_events (event_name, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_application_events_attributes_gin
    ON public.application_events USING gin (attributes_safe);

CREATE TABLE IF NOT EXISTS public.evaluation_suites (
    evaluation_suite_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    suite_name text NOT NULL,
    suite_version integer NOT NULL CHECK (suite_version > 0),
    description text,
    is_active boolean NOT NULL DEFAULT true,
    created_by uuid REFERENCES public.support_users(user_id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (suite_name, suite_version)
);

CREATE TABLE IF NOT EXISTS public.evaluation_cases (
    evaluation_case_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    evaluation_suite_id uuid NOT NULL
        REFERENCES public.evaluation_suites(evaluation_suite_id) ON DELETE CASCADE,
    case_key text NOT NULL,
    input_message_redacted text NOT NULL,
    expected_intent text,
    expected_route text,
    expected_doc_ids jsonb NOT NULL DEFAULT '[]'::jsonb
        CHECK (jsonb_typeof(expected_doc_ids) = 'array'),
    expected_facts jsonb NOT NULL DEFAULT '[]'::jsonb
        CHECK (jsonb_typeof(expected_facts) = 'array'),
    expected_escalation boolean,
    safety_tags jsonb NOT NULL DEFAULT '[]'::jsonb
        CHECK (jsonb_typeof(safety_tags) = 'array'),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (evaluation_suite_id, case_key)
);

CREATE TABLE IF NOT EXISTS public.evaluation_runs (
    evaluation_run_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    evaluation_suite_id uuid NOT NULL
        REFERENCES public.evaluation_suites(evaluation_suite_id) ON DELETE RESTRICT,
    git_commit_sha text,
    model_config_safe jsonb NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(model_config_safe) = 'object'),
    run_status text NOT NULL DEFAULT 'started'
        CHECK (run_status IN ('started', 'completed', 'failed', 'cancelled')),
    total_cases integer CHECK (total_cases IS NULL OR total_cases >= 0),
    passed_cases integer CHECK (passed_cases IS NULL OR passed_cases >= 0),
    aggregate_metrics jsonb NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(aggregate_metrics) = 'object'),
    started_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_evaluation_runs_suite_started
    ON public.evaluation_runs (evaluation_suite_id, started_at DESC);

CREATE TABLE IF NOT EXISTS public.evaluation_results (
    evaluation_result_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    evaluation_run_id uuid NOT NULL
        REFERENCES public.evaluation_runs(evaluation_run_id) ON DELETE CASCADE,
    evaluation_case_id uuid NOT NULL
        REFERENCES public.evaluation_cases(evaluation_case_id) ON DELETE CASCADE,
    passed boolean NOT NULL,
    actual_intent text,
    actual_route text,
    actual_doc_ids jsonb NOT NULL DEFAULT '[]'::jsonb
        CHECK (jsonb_typeof(actual_doc_ids) = 'array'),
    actual_escalation boolean,
    metric_values jsonb NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(metric_values) = 'object'),
    failure_reasons jsonb NOT NULL DEFAULT '[]'::jsonb
        CHECK (jsonb_typeof(failure_reasons) = 'array'),
    latency_ms integer CHECK (latency_ms IS NULL OR latency_ms >= 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (evaluation_run_id, evaluation_case_id)
);

CREATE OR REPLACE VIEW public.pi1_daily_pipeline_metrics AS
SELECT
    date_trunc('day', started_at) AS metric_day,
    count(*) AS request_count,
    count(*) FILTER (WHERE final_outcome = 'answered') AS answered_count,
    count(*) FILTER (WHERE final_outcome = 'clarified') AS clarified_count,
    count(*) FILTER (WHERE final_outcome = 'escalated') AS escalated_count,
    count(*) FILTER (WHERE final_outcome = 'failed') AS failed_count,
    percentile_cont(0.50) WITHIN GROUP (ORDER BY total_latency_ms)
        FILTER (WHERE total_latency_ms IS NOT NULL) AS p50_latency_ms,
    percentile_cont(0.95) WITHIN GROUP (ORDER BY total_latency_ms)
        FILTER (WHERE total_latency_ms IS NOT NULL) AS p95_latency_ms
FROM public.pipeline_runs
GROUP BY date_trunc('day', started_at);

CREATE OR REPLACE VIEW public.pi1_daily_feedback_metrics AS
SELECT
    date_trunc('day', created_at) AS metric_day,
    count(*) FILTER (WHERE feedback_status = 'active') AS feedback_count,
    count(*) FILTER (
        WHERE feedback_status = 'active' AND rating = 'positive'
    ) AS positive_count,
    count(*) FILTER (
        WHERE feedback_status = 'active' AND rating = 'negative'
    ) AS negative_count
FROM public.feedback
GROUP BY date_trunc('day', created_at);

COMMIT;
