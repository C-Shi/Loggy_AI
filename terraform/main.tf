terraform {
  required_providers {
    google = "~> 7.0"
  }

  backend "gcs" {
  }
}

provider "google" {
  project = var.project_id
}

data "google_project" "project" {
  project_id = var.project_id
}


data "google_cloud_run_v2_service" "loggy_ai" {
  name     = "loggy-ai-service"
  location = "us-west1"
}

data "google_cloud_run_v2_service" "loggy_ai_dashboard" {
  name     = "loggy-ai-dashboard"
  location = "us-west1"
}

resource "google_service_account" "sa_loggy_ai_runtime" {
  account_id   = "sa-loggy-ai-runtime"
  description  = "service account to run Loggy AI"
  display_name = "sa-loggy-ai-runtime"
}

resource "google_project_iam_member" "loggy_ai_sa_iam" {
  project = var.project_id
  role    = "roles/logging.viewer"
  member  = "serviceAccount:${google_service_account.sa_loggy_ai_runtime.email}"
}

resource "google_service_account" "sa_loggy_ai_caller" {
  account_id   = "sa-loggy-ai-caller"
  description  = "service account to execute cloud run"
  display_name = "sa-loggy-ai-caller"
}

resource "google_cloud_run_v2_service_iam_member" "loggy_ai_caller_iam" {
  name     = data.google_cloud_run_v2_service.loggy_ai.name
  location = data.google_cloud_run_v2_service.loggy_ai.location
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.sa_loggy_ai_caller.email}"
}


resource "google_artifact_registry_repository" "loggy-ai-service" {
  location               = "us-west1"
  repository_id          = "loggy-ai-service"
  description            = "repository to store loggy-ai-service"
  format                 = "docker"
  cleanup_policy_dry_run = false
  cleanup_policies {
    id     = "keep-one"
    action = "KEEP"
    most_recent_versions {
      keep_count = 1
    }
  }

  vulnerability_scanning_config {
    enablement_config = "DISABLED"
  }

}

resource "google_artifact_registry_repository" "loggy-ai-dashboard" {
  location      = "us-west1"
  repository_id = "loggy-ai-dashboard"
  description   = "repository to store loggy-ai-dashboard"
  format        = "docker"
  cleanup_policies {
    id     = "keep-one"
    action = "KEEP"
    most_recent_versions {
      keep_count = 1
    }
  }

  vulnerability_scanning_config {
    enablement_config = "DISABLED"
  }
}
resource "google_secret_manager_secret" "gemini_key" {
  secret_id = "gemini-key"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_iam_member" "cloud_run_accessor" {
  project   = var.project_id
  secret_id = google_secret_manager_secret.gemini_key.id
  role      = "roles/secretmanager.secretAccessor"

  member = "serviceAccount:${google_service_account.sa_loggy_ai_runtime.email}"
}

resource "google_pubsub_topic" "loggy_ai_pubsub" {
  name = "loggy-ai-pubsub"
}

resource "google_pubsub_topic_iam_member" "sink_write" {
  topic  = google_pubsub_topic.loggy_ai_pubsub.name
  role   = "roles/pubsub.publisher"
  member = google_logging_project_sink.loggy_ai_sink.writer_identity
}

resource "google_logging_project_sink" "loggy_ai_sink" {
  name = "loggy_ai_sink"

  destination = "pubsub.googleapis.com/projects/${var.project_id}/topics/${google_pubsub_topic.loggy_ai_pubsub.name}"

  filter = "resource.labels.service_name != 'loggy-ai-service' AND severity >= ERROR"

  unique_writer_identity = true
}

resource "google_eventarc_trigger" "loggy_ai_eventarc" {
  name     = "loggy-ai-trigger"
  location = "us-west1"
  matching_criteria {
    attribute = "type"
    value     = "google.cloud.pubsub.topic.v1.messagePublished"
  }
  destination {
    cloud_run_service {
      service = data.google_cloud_run_v2_service.loggy_ai.name
      region  = data.google_cloud_run_v2_service.loggy_ai.location
      path    = "/trigger"
    }
  }
  transport {
    pubsub {
      topic = google_pubsub_topic.loggy_ai_pubsub.id
    }
  }
  retry_policy {
    max_attempts = 1
  }

  service_account = google_service_account.sa_loggy_ai_caller.email
}

resource "google_firestore_database" "loggy_ai_report" {
  project          = var.project_id
  name             = "loggy-ai-report"
  location_id      = "us-west1"
  type             = "FIRESTORE_NATIVE"
  database_edition = "STANDARD"
  concurrency_mode = "OPTIMISTIC"
}

resource "google_project_iam_member" "loggy_ai_report_firestore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.sa_loggy_ai_runtime.email}"

  condition {
    title       = "loggy-ai-report firestore access"
    description = "Grant read/write access only to the loggy-ai-report Firestore database"
    expression  = "resource.name == \"projects/${var.project_id}/databases/loggy-ai-report\""
  }
}

# Covers: service_name == + severity == + created_at >= ORDER BY created_at DESC
resource "google_firestore_index" "reports_dedup" {
  project    = var.project_id
  database   = google_firestore_database.loggy_ai_report.name
  collection = "reports"

  fields {
    field_path = "service_name"
    order      = "ASCENDING"
  }

  fields {
    field_path = "severity"
    order      = "ASCENDING"
  }

  fields {
    field_path = "created_at"
    order      = "DESCENDING"
  }
}

# Covers: signature == + created_at >= ORDER BY created_at DESC
resource "google_firestore_index" "reports_by_signature" {
  project    = var.project_id
  database   = google_firestore_database.loggy_ai_report.name
  collection = "reports"

  fields {
    field_path = "signature"
    order      = "ASCENDING"
  }

  fields {
    field_path = "created_at"
    order      = "DESCENDING"
  }
}

resource "google_pubsub_topic" "loggy_ai_dlq" {
  name = "loggy-ai-dlq"

  message_retention_duration = "604800s"
}

resource "google_pubsub_subscription" "loggy_ai_dlq_subscription" {
  name                       = "loggy-ai-dlq-subscription"
  project                    = var.project_id
  topic                      = google_pubsub_topic.loggy_ai_dlq.name
  message_retention_duration = "604800s"
  retry_policy {
    maximum_backoff = "600s"
    minimum_backoff = "10s"
  }

  expiration_policy {
    ttl = ""
  }
}

resource "google_pubsub_topic_iam_member" "loggy_ai_dlq_writer" {
  topic  = google_pubsub_topic.loggy_ai_dlq.name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

resource "google_pubsub_subscription_iam_member" "loggy_ai_dlq_reader" {
  subscription = google_pubsub_subscription.eventarc_trigger_subscription.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

import {
  to = google_pubsub_subscription.eventarc_trigger_subscription
  id = "projects/${var.project_id}/subscriptions/eventarc-us-west1-loggy-ai-trigger-sub-105"
}

resource "google_pubsub_subscription" "eventarc_trigger_subscription" {
  name                       = "eventarc-us-west1-loggy-ai-trigger-sub-105"
  project                    = var.project_id
  topic                      = google_pubsub_topic.loggy_ai_pubsub.name
  message_retention_duration = "86400s" # 1 day

  retry_policy {
    maximum_backoff = "600s"
    minimum_backoff = "10s"
  }

  dead_letter_policy {
    max_delivery_attempts = 5
    dead_letter_topic     = google_pubsub_topic.loggy_ai_dlq.id
  }

  lifecycle {
    # Eventarc owns push endpoint / OIDC — do not let TF overwrite it
    ignore_changes = [push_config]
  }
}

# IAP for loggy-ai-dashboard (Cloud Run itself is deployed by GitHub Actions with --iap).
# Prerequisite: service must already exist (data source above) with --no-allow-unauthenticated.

# Let the IAP service agent invoke Cloud Run after a user passes the IAP allowlist.
resource "google_cloud_run_v2_service_iam_member" "loggy_ai_dashboard_iap_invoker" {
  project  = var.project_id
  name     = data.google_cloud_run_v2_service.loggy_ai_dashboard.name
  location = data.google_cloud_run_v2_service.loggy_ai_dashboard.location
  role     = "roles/run.invoker"
  member   = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-iap.iam.gserviceaccount.com"
}

# Authoritative role binding is created once with an empty member list; members are
# managed only in the GCP console afterward so emails never appear in git.
resource "google_iap_web_cloud_run_service_iam_binding" "loggy_ai_dashboard_iap_access" {
  project                = var.project_id
  location               = data.google_cloud_run_v2_service.loggy_ai_dashboard.location
  cloud_run_service_name = data.google_cloud_run_v2_service.loggy_ai_dashboard.name
  role                   = "roles/iap.httpsResourceAccessor"
  members                = []

  lifecycle {
    ignore_changes = [members]
  }
}


