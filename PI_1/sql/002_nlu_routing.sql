BEGIN;

CREATE TABLE IF NOT EXISTS public.routing_policies (
    routing_policy_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    policy_name text NOT NULL,
    policy_version integer NOT NULL CHECK (policy_version > 0),
    is_active boolean NOT NULL DEFAULT false,
    high_confidence_threshold numeric(5,4) NOT NULL DEFAULT 0.8500
        CHECK (high_confidence_threshold BETWEEN 0 AND 1),
    low_confidence_threshold numeric(5,4) NOT NULL DEFAULT 0.6500
        CHECK (low_confidence_threshold BETWEEN 0 AND 1),
    high_risk_intents jsonb NOT NULL DEFAULT '[]'::jsonb
        CHECK (jsonb_typeof(high_risk_intents) = 'array'),
    intent_route_map jsonb NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(intent_route_map) = 'object'),
    policy_config jsonb NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(policy_config) = 'object'),
    created_by uuid REFERENCES public.support_users(user_id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    activated_at timestamptz,
    UNIQUE (policy_name, policy_version),
    CHECK (low_confidence_threshold <= high_confidence_threshold)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_routing_policies_one_active
    ON public.routing_policies (policy_name)
    WHERE is_active;

CREATE TABLE IF NOT EXISTS public.nlu_results (
    nlu_result_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id uuid NOT NULL UNIQUE
        REFERENCES public.pipeline_runs(run_id) ON DELETE CASCADE,
    model_name text NOT NULL,
    model_version text NOT NULL,
    intent_code text NOT NULL,
    intent_confidence numeric(7,6) NOT NULL
        CHECK (intent_confidence BETWEEN 0 AND 1),
    entities jsonb NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(entities) = 'object'),
    sentiment text
        CHECK (sentiment IS NULL OR sentiment IN (
            'positive', 'neutral', 'negative', 'frustrated'
        )),
    sentiment_score numeric(7,6)
        CHECK (sentiment_score IS NULL OR sentiment_score BETWEEN -1 AND 1),
    urgency text NOT NULL DEFAULT 'normal'
        CHECK (urgency IN ('low', 'normal', 'high', 'critical')),
    department text,
    recommended_action text,
    escalation_suggested boolean NOT NULL DEFAULT false,
    inference_latency_ms integer NOT NULL
        CHECK (inference_latency_ms >= 0),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_nlu_results_intent_created
    ON public.nlu_results (intent_code, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_nlu_results_low_confidence
    ON public.nlu_results (intent_confidence, created_at DESC)
    WHERE intent_confidence < 0.6500;
CREATE INDEX IF NOT EXISTS idx_nlu_results_entities_gin
    ON public.nlu_results USING gin (entities);

CREATE TABLE IF NOT EXISTS public.routing_decisions (
    routing_decision_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id uuid NOT NULL UNIQUE
        REFERENCES public.pipeline_runs(run_id) ON DELETE CASCADE,
    nlu_result_id uuid NOT NULL UNIQUE
        REFERENCES public.nlu_results(nlu_result_id) ON DELETE CASCADE,
    routing_policy_id uuid
        REFERENCES public.routing_policies(routing_policy_id) ON DELETE SET NULL,
    selected_route text NOT NULL
        CHECK (selected_route IN ('rag', 'clarify', 'human', 'direct_response')),
    decision_reason_code text NOT NULL,
    decision_explanation_safe text,
    threshold_snapshot jsonb NOT NULL
        CHECK (jsonb_typeof(threshold_snapshot) = 'object'),
    is_high_risk boolean NOT NULL DEFAULT false,
    decided_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_routing_decisions_route_created
    ON public.routing_decisions (selected_route, decided_at DESC);
CREATE INDEX IF NOT EXISTS idx_routing_decisions_reason_created
    ON public.routing_decisions (decision_reason_code, decided_at DESC);

COMMIT;

