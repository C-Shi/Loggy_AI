async function readJson(res) {
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(body.detail || `Request failed (${res.status})`);
  }
  return body;
}

export async function fetchReports(params = {}) {
  const query = new URLSearchParams();
  if (params.severity) query.set("severity", params.severity);
  if (params.service_name) query.set("service_name", params.service_name);

  const qs = query.toString();
  const res = await fetch(`/api/reports${qs ? `?${qs}` : ""}`);
  return readJson(res);
}

export async function fetchReport(id) {
  const res = await fetch(`/api/reports/${id}`);
  return readJson(res);
}
