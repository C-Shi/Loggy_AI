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

data "google_cloud_run_v2_service" "loggy_ai" {
  name     = "loggy-ai-service"
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


resource "google_artifact_registry_repository" "loggy-ai-image" {
  location               = "us-west1"
  repository_id          = "loggy-ai-image"
  description            = "repository to store loggy-ai-image"
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


