const BASE = import.meta.env.VITE_API_BASE_URL || '';

export interface LocationData {
  ip: string;
  city: string;
  region: string;
  isp: string;
  lat: number;
  lon: number;
  is_india: boolean;
  source: string;
}

export interface AnchorInfo {
  id: string;
  city: string;
  lat: number;
  lon: number;
}

export interface LocateResponse {
  location: LocationData;
  nearest_anchor: AnchorInfo;
}

export interface QueryResult {
  domain?: string;
  record_type?: string;
  answers?: string[];
  query_time_ms?: number | null;
  resolver_used?: string;
  status?: string;
  raw_output?: string;
  anchor_id?: string;
  error?: string;
  error_detail?: string;
  anchor_used?: AnchorInfo;
  selection_method?: string;
}

export interface HealthResponse {
  status: string;
  anchor_count: number;
}

export async function fetchLocate(): Promise<LocateResponse> {
  const res = await fetch(`${BASE}/api/locate`);
  if (!res.ok) throw new Error(`Locate failed: ${res.status}`);
  return res.json();
}

export async function fetchAnchors(): Promise<AnchorInfo[]> {
  const res = await fetch(`${BASE}/api/anchors`);
  if (!res.ok) throw new Error(`Anchors failed: ${res.status}`);
  return res.json();
}

export async function fetchQuery(
  domain: string,
  recordType: string,
  anchorId?: string
): Promise<QueryResult> {
  const body: Record<string, string> = { domain, record_type: recordType };
  if (anchorId) body.anchor_id = anchorId;

  const res = await fetch(`${BASE}/api/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`Query failed: ${res.status}`);
  return res.json();
}

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch(`${BASE}/api/health`);
  if (!res.ok) throw new Error(`Health failed: ${res.status}`);
  return res.json();
}
