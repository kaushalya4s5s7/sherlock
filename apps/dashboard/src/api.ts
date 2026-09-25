import type { CaseRow, ClosedCase, Investigation } from "./types";

export async function health(): Promise<{ transactions: number; closed_cases: number; graph: string }> {
  const response = await fetch("/api/health");
  if (!response.ok) throw new Error("The case service did not answer.");
  return response.json();
}

export async function listCases(): Promise<CaseRow[]> {
  const response = await fetch("/api/cases");
  if (!response.ok) throw new Error("The case list did not load.");
  const body = await response.json();
  return body.cases;
}

export type PipelineStep = {
  id: string;
  label: string;
  detail: string;
  status: "done" | "running" | "waiting";
};

export async function caseProgress(caseId: string): Promise<PipelineStep[]> {
  const response = await fetch(`/api/cases/${caseId}/progress`);
  if (!response.ok) throw new Error("The investigation progress did not load.");
  const body = await response.json();
  return body.steps;
}

export async function closedCase(caseId: string): Promise<ClosedCase> {
  const response = await fetch(`/api/closed/${caseId}`);
  if (!response.ok) throw new Error(`${caseId} is not in the closed history.`);
  return response.json();
}

export async function openCase(caseId: string): Promise<Investigation> {
  const saved = await fetch(`/api/cases/${caseId}`);
  if (saved.ok) return saved.json();
  return runCase(caseId);
}

export async function runCase(caseId: string): Promise<Investigation> {
  const response = await fetch(`/api/cases/${caseId}/run`, { method: "POST" });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail.detail || `Could not investigate ${caseId}.`);
  }
  return response.json();
}

export async function approve(caseId: string, action: string): Promise<Investigation> {
  const response = await fetch(`/api/cases/${caseId}/approve`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ action }),
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail.detail || "That approval was refused.");
  }
  const follow = await fetch(`/api/cases/${caseId}`);
  if (!follow.ok) throw new Error("The case was approved, then the desk could not read it back.");
  return follow.json();
}
