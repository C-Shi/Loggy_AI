import { Firestore } from "@google-cloud/firestore";

const PROJECT_ID =
  process.env.PROJECT_ID ||
  process.env.GOOGLE_CLOUD_PROJECT ||
  "devops-cert-440119";

const DATABASE_ID = process.env.FIRESTORE_DATABASE || "loggy-ai-report";
const COLLECTION = "reports";

const db = new Firestore({
  projectId: PROJECT_ID,
  databaseId: DATABASE_ID,
});

/** Convert Firestore Timestamps / nested values into JSON-safe forms. */
function serialize(value) {
  if (value == null) return value;
  if (typeof value.toDate === "function") {
    return value.toDate().toISOString();
  }
  if (Array.isArray(value)) return value.map(serialize);
  if (value instanceof Date) return value.toISOString();
  if (typeof value === "object") {
    const out = {};
    for (const [k, v] of Object.entries(value)) {
      out[k] = serialize(v);
    }
    return out;
  }
  return value;
}

function docToReport(doc) {
  return { id: doc.id, ...serialize(doc.data()) };
}

export async function listReports({ severity, service_name } = {}) {
  let query = db.collection(COLLECTION).orderBy("created_at", "desc");

  // Firestore requires equality filters to be combined carefully with orderBy.
  // Fetch ordered, then filter in memory for simplicity (fine for dashboard volumes).
  const snap = await query.get();
  let reports = snap.docs.map(docToReport);

  if (severity) {
    const s = String(severity).toUpperCase();
    reports = reports.filter((r) => (r.severity || "").toUpperCase() === s);
  }
  if (service_name) {
    reports = reports.filter((r) => r.service_name === service_name);
  }

  return reports;
}

export async function getReport(id) {
  const snap = await db.collection(COLLECTION).doc(id).get();
  if (!snap.exists) return null;
  return docToReport(snap);
}

export function getFirestoreConfig() {
  return { projectId: PROJECT_ID, databaseId: DATABASE_ID, collection: COLLECTION };
}
