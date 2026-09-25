export type Action = { action: string; route: string; reason: string };

export type ClosedCase = {
  case_id: string;
  customer_id: string;
  card_id: string;
  outcome: string;
  pattern: string;
  txn_ids: string[];
  connected: string[];
  exposure_usd: number;
  actions: string[];
  notes: string;
};

export type CaseAction = { action: string; route: string };

export type CaseResult = {
  verdict: string;
  pattern: string;
  exposure_usd: number;
  written_to_graph: boolean;
  graph_case_id: string;
  sar_file: boolean;
  initial: CaseAction[];
  final: CaseAction[];
  what_changed: string;
};

export type CaseRow = {
  case_id: string;
  customer_id: string;
  card_id: string;
  trigger_type: string;
  risk_score: string;
  trigger_text: string;
  ran: boolean;
  decision: string | null;
  result?: CaseResult | null;
};

export type Investigation = {
  answer: {
    case_id: string;
    case: {
      status: string;
      verdict: string;
      fraud_probability: number;
      pattern: string;
      pattern_description: string;
      exposure_usd: number;
      evidence: { claim: string; source: string; ref: string; entity_ids: string[] }[];
      connected_card_ids?: string[];
      similar_prior_cases: string[];
      summary: string;
      written_to_graph: boolean;
      graph_case_id: string;
      affected_txn_ids: string[];
    };
    evidence_requests: { type: string; assumed_response: string }[];
    next_best_actions: {
      initial: Action[];
      final: Action[];
      what_changed: string;
    };
    sar: { file: boolean; narrative: string; reason?: string };
    stop_reason: string;
    tokens: number;
    latency_s: number;
  };
  demo: {
    register: { rule: string; fired: boolean; because: string }[];
    waterfall: { name: string; delta: number; p: number }[];
    commitment: { text: string; family: string };
    reply_assumption: string;
    counterfactuals: { reply: string; label: string; actions: string[]; p: number }[];
    exposure: number;
    profile: string;
    trigger: string;
    history_n: number;
    flagged: {
      txn_id: string;
      ts: string;
      amount: number;
      channel: string;
      region: string;
      score: number | string | null;
    };
    approved?: string[];
    approval: string;
    connected?: string[];
    hop?: string;
    why_not?: { pattern: string; reason: string }[];
    control_fallback?: boolean;
    language_fallback?: boolean;
    memory_matched?: boolean;
    pattern_description: string;
    trace?: {
      result: string;
      execution: string[];
      anomaly: string;
      diagnosis: { kind: string; title: string; because: string };
    };
  };
};
