import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { fetchReports } from "../api.js";
import ImpactChart from "../components/ImpactChart.jsx";
import { formatTimestamp, normalizeImpact } from "../lib/format.js";

export default function ReportList() {
  const [reports, setReports] = useState([]);
  const [severity, setSeverity] = useState("");
  const [service, setService] = useState("");
  const [impact, setImpact] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    fetchReports()
      .then((data) => {
        if (!cancelled) setReports(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const services = useMemo(
    () =>
      [...new Set(reports.map((r) => r.service_name).filter(Boolean))].sort(),
    [reports]
  );

  const filtered = useMemo(() => {
    return reports.filter((r) => {
      if (severity && (r.severity || "").toUpperCase() !== severity) return false;
      if (service && r.service_name !== service) return false;
      if (impact && normalizeImpact(r.business_impact) !== impact) return false;
      return true;
    });
  }, [reports, severity, service, impact]);

  const stats = useMemo(() => {
    const totalIncidents = reports.reduce(
      (sum, r) => sum + (Number(r.incident_count) || 1),
      0
    );
    const critical = reports.filter(
      (r) => normalizeImpact(r.business_impact) === "CRITICAL"
    ).length;
    const high = reports.filter(
      (r) => normalizeImpact(r.business_impact) === "HIGH"
    ).length;
    const servicesTouched = new Set(
      reports.map((r) => r.service_name).filter(Boolean)
    ).size;
    return {
      reports: reports.length,
      totalIncidents,
      critical,
      high,
      servicesTouched,
    };
  }, [reports]);

  return (
    <>
      <div className="page-header">
        <div>
          <p className="eyebrow">Incident intelligence</p>
          <h1 className="page-title">Operations dashboard</h1>
          <p className="page-desc">
            AI-analyzed production incidents from Firestore reports.
          </p>
        </div>
      </div>

      <section className="kpi-row">
        <article className="kpi-card">
          <p className="kpi-label">Open reports</p>
          <p className="kpi-value">{loading ? "—" : stats.reports}</p>
        </article>
        <article className="kpi-card">
          <p className="kpi-label">Total occurrences</p>
          <p className="kpi-value">{loading ? "—" : stats.totalIncidents}</p>
        </article>
        <article className="kpi-card kpi-critical">
          <p className="kpi-label">Critical reports</p>
          <p className="kpi-value">{loading ? "—" : stats.critical}</p>
        </article>
        <article className="kpi-card kpi-high">
          <p className="kpi-label">High impact</p>
          <p className="kpi-value">{loading ? "—" : stats.high}</p>
        </article>
        <article className="kpi-card">
          <p className="kpi-label">Services</p>
          <p className="kpi-value">{loading ? "—" : stats.servicesTouched}</p>
        </article>
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>Incidents by business impact</h2>
            <p className="panel-sub">
              Sum of <code>incident_count</code> grouped by{" "}
              <code>business_impact</code>
            </p>
          </div>
        </div>
        {loading ? (
          <p className="loading">Loading chart…</p>
        ) : (
          <ImpactChart reports={filtered} />
        )}
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>Incident reports</h2>
            <p className="panel-sub">
              {filtered.length} of {reports.length} reports
            </p>
          </div>
        </div>

        <div className="filters">
          <label>
            Log severity
            <select
              value={severity}
              onChange={(e) => setSeverity(e.target.value)}
            >
              <option value="">All</option>
              <option value="ERROR">ERROR</option>
              <option value="WARNING">WARNING</option>
              <option value="CRITICAL">CRITICAL</option>
            </select>
          </label>
          <label>
            Business impact
            <select value={impact} onChange={(e) => setImpact(e.target.value)}>
              <option value="">All</option>
              <option value="CRITICAL">CRITICAL</option>
              <option value="HIGH">HIGH</option>
              <option value="MEDIUM">MEDIUM</option>
              <option value="LOW">LOW</option>
            </select>
          </label>
          <label>
            Service
            <select value={service} onChange={(e) => setService(e.target.value)}>
              <option value="">All</option>
              {services.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </label>
        </div>

        {error && <p className="error">{error}</p>}
        {loading && <p className="loading">Loading reports…</p>}

        {!loading && !error && (
          <div className="table-wrap">
            <table className="report-table">
              <thead>
                <tr>
                  <th>Impact</th>
                  <th>Severity</th>
                  <th>Service</th>
                  <th>Summary</th>
                  <th>Count</th>
                  <th>Last seen</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((r) => {
                  const impactLevel = normalizeImpact(r.business_impact);
                  return (
                    <tr key={r.id}>
                      <td>
                        <span className={`badge ${impactLevel}`}>
                          {impactLevel}
                        </span>
                      </td>
                      <td>
                        <span className="mono muted">
                          {r.severity || "—"}
                        </span>
                      </td>
                      <td className="service-cell">
                        {r.service_name || "—"}
                      </td>
                      <td className="summary-cell">
                        {r.operational_summary}
                      </td>
                      <td className="mono">{r.incident_count ?? 1}</td>
                      <td className="muted">
                        {formatTimestamp(
                          r.last_seen_timestamp || r.created_at
                        )}
                      </td>
                      <td>
                        <Link className="row-action" to={`/reports/${r.id}`}>
                          View
                        </Link>
                      </td>
                    </tr>
                  );
                })}
                {filtered.length === 0 && (
                  <tr>
                    <td colSpan={7} className="empty-row">
                      No reports match these filters.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
