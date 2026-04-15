terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.47.0, <6.0"
    }

    helm = {
      source = "hashicorp/helm"
      version = ">= 2.9, < 3.0"
    }

    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = ">= 2.20"
    }
  }


  # ##  Used for end-to-end testing on project; update to suit your needs
  # backend "s3" {
  #   bucket = "terraform-ssp-github-actions-state"
  #   region = "us-east-1"
  #   key    = "e2e/istio/terraform.tfstate"
    
  
  required_version = ">= 1.3"
}
