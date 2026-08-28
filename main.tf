terraform {
  required_version = ">= 1.5"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# -------
# APIs
# -------

resource "google_project_service" "apis" {
  for_each = toset([
    "cloudresourcemanager.googleapis.com",
    "iam.googleapis.com",
    "bigquery.googleapis.com",
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
  ])

  service = each.value

  disable_on_destroy = false
}

# ------------
# BigQuery
# ------------

resource "google_bigquery_dataset" "stock_data" {
  dataset_id = "stock_data"
  location   = var.region

  depends_on = [google_project_service.apis]
}

resource "google_bigquery_table" "daily_prices" {
  dataset_id = google_bigquery_dataset.stock_data.dataset_id
  table_id   = "daily_prices"

  deletion_protection = false

  schema = jsonencode([
    { name = "trade_date",  type = "DATE",    mode = "REQUIRED" },
    { name = "symbol",      type = "STRING",  mode = "REQUIRED" },
    { name = "close_price", type = "NUMERIC", mode = "REQUIRED" },
    { name = "volume",      type = "INTEGER", mode = "REQUIRED" },
    { name = "fetched_at",  type = "TIMESTAMP", mode = "REQUIRED" },
  ])
}

# ------------------
# Service account
# ------------------

resource "google_service_account" "pipeline" {
  account_id   = "nifty-pipeline-sa"
  display_name = "Nifty daily snapshot pipeline"
}

# Write access
resource "google_bigquery_dataset_iam_member" "pipeline_data_editor" {
  dataset_id = google_bigquery_dataset.stock_data.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.pipeline.email}"
}

resource "google_project_iam_member" "pipeline_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.pipeline.email}"
}

# -------------------------
# Artifact Registry
# -------------------------

resource "google_artifact_registry_repository" "images" {
  repository_id = "nifty-snapshot"
  location      = var.region
  format        = "DOCKER"

  depends_on = [google_project_service.apis]
}

# --------------
# Cloud Run
# --------------

resource "google_cloud_run_v2_service" "snapshot" {
  name     = "nifty-daily-snapshot"
  location = var.region

  template {
    service_account = google_service_account.pipeline.email
    timeout         = "300s"

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.images.repository_id}/nifty-snapshot:${var.image_tag}"

      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
      }
    }
  }

  depends_on = [google_project_service.apis]
}

# ------------
# Outputs
# ------------

output "service_url" {
  value = google_cloud_run_v2_service.snapshot.uri
}

output "bigquery_table" {
  value = "${var.project_id}.${google_bigquery_dataset.stock_data.dataset_id}.${google_bigquery_table.daily_prices.table_id}"
}