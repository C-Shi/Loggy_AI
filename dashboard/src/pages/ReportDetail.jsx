import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchReport } from "../api.js";
import { formatTimestamp, normalizeImpact } from "../lib/format.js";

export default function ReportDetail() {
  const { id } = useParams();
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    fetchReport(id)
      .then((data) => {
        if (!cancelled) setReport(data);
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
  }, [id]);

  if (loading) return <p className="loading">Loading report…</p>;
  if (error) return <p className="error">{error}</p>;
  if (!report) return null;

  const impactLevel = normalizeImpact(report.business_impact);

  return (
    <>
      <Link to="/" className="back-link">
        ← Back to incidents
      </Link>

      <div className="page-header">
        <div>
          <p className="eyebrow">Report detail</p>
          <h1 className="page-title">
            {report.service_name || "Unknown service"}
          </h1>
          <p className="page-desc">{report.operational_summary}</p>
        </div>
        <div className="header-meta">
          <span className={`badge ${impactLevel}`}>{impactLevel}</span>
          <span className="meta-pill">{report.severity || "n/a"}</span>
          <span className="meta-pill">
            {report.incident_count ?? 1} occurrences
          </span>
        </div>
      </div>

      <section className="detail-layout">
        <article className="panel">
          <h2>Analysis</h2>
          <dl className="detail-grid">
            <div>
              <dt>Root cause</dt>
              <dd>{report.root_cause || "—"}</dd>
            </div>
            <div>
              <dt>AI suggestion</dt>
              <dd>{report.ai_suggestion || "—"}</dd>
            </div>
            <div>
              <dt>Business impact</dt>
              <dd>
                <span className={`badge ${impactLevel}`}>{impactLevel}</span>
                {report.business_impact &&
                  report.business_impact !== impactLevel && (
                    <span className="muted"> ({report.business_impact})</span>
                  )}
              </dd>
            </div>
          </dl>
        </article>

        <article className="panel">
          <h2>Timeline</h2>
          <dl className="detail-grid">
            <div>
              <dt>First seen</dt>
              <dd>{formatTimestamp(report.first_seen_timestamp)}</dd>
            </div>
            <div>
              <dt>Last seen</dt>
              <dd>{formatTimestamp(report.last_seen_timestamp)}</dd>
            </div>
            <div>
              <dt>Report created</dt>
              <dd>{formatTimestamp(report.created_at)}</dd>
            </div>
            <div>
              <dt>Signature</dt>
              <dd className="mono">{report.signature || "—"}</dd>
            </div>
            <div>
              <dt>Report ID</dt>
              <dd className="mono">{report.id}</dd>
            </div>
          </dl>
        </article>
      </section>

      <section className="panel">
        <h2>Action plan</h2>
        <ol className="action-list">
          {(report.action_plan || []).map((step) => (
            <li key={step.step}>
              <div className="action-step">
                <span className="action-index">Step {step.step}</span>
                <strong>{step.action}</strong>
                {step.warning && (
                  <div className="action-warning">Warning: {step.warning}</div>
                )}
              </div>
            </li>
          ))}
          {(report.action_plan || []).length === 0 && (
            <p className="muted">No action plan recorded.</p>
          )}
        </ol>
      </section>

      {report.log_message && (
        <section className="panel">
          <h2>Source log message</h2>
          <pre className="log-block">{report.log_message}</pre>
        </section>
      )}
    </>
  );
}
