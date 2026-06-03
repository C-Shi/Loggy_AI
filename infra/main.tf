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


