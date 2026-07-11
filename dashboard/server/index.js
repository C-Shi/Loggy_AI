import express from "express";
import path from "path";
import { fileURLToPath } from "url";
import { getReport, getFirestoreConfig, listReports } from "./firestore.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const app = express();
const PORT = process.env.PORT || 3001;
const isProd = process.env.NODE_ENV === "production";

app.get("/api/health", (_req, res) => {
  res.json({ status: "ok", firestore: getFirestoreConfig() });
});

app.get("/api/reports", async (req, res) => {
  try {
    const reports = await listReports({
      severity: req.query.severity,
      service_name: req.query.service_name,
    });
    res.json(reports);
  } catch (err) {
    console.error("listReports failed:", err);
    res.status(500).json({
      detail: err.message || "Failed to load reports from Firestore",
    });
  }
});

app.get("/api/reports/:id", async (req, res) => {
  try {
    const report = await getReport(req.params.id);
    if (!report) {
      return res.status(404).json({ detail: "Report not found" });
    }
    res.json(report);
  } catch (err) {
    console.error("getReport failed:", err);
    res.status(500).json({
      detail: err.message || "Failed to load report from Firestore",
    });
  }
});

if (isProd) {
  const dist = path.join(__dirname, "..", "dist");
  app.use(express.static(dist));
  app.get(/.*/, (_req, res) => {
    res.sendFile(path.join(dist, "index.html"));
  });
}

app.listen(PORT, () => {
  const cfg = getFirestoreConfig();
  console.log(`Dashboard API listening on http://localhost:${PORT}`);
  console.log(
    `Firestore: project=${cfg.projectId} db=${cfg.databaseId} collection=${cfg.collection}`
  );
});
