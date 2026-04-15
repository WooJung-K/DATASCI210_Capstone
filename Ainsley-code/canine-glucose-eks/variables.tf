variable "region" {
  description = "AWS region to deploy into."
  type        = string
  default     = "us-east-1"
}

variable "istio_chart_url" {
  description = "Helm repository URL for Istio charts."
  type        = string
  default     = "https://istio-release.storage.googleapis.com/charts"
}

variable "istio_chart_version" {
  description = "Istio chart version to deploy."
  type        = string
  default     = "1.29.0"
}

variable "cloudfront_enabled" {
  type    = bool
  default = true
}

variable "cloudfront_price_class" {
  type    = string
  default = "PriceClass_100"
}