variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "Region for all resources"
  type        = string
  default     = "asia-south1"
}

variable "image_tag" {
  description = "Tag of the container image in Artifact Registry"
  type        = string
  default     = "latest"
}