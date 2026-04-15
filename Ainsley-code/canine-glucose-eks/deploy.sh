#!/bin/bash
set -euo pipefail

# Check if infra plan is reasonable
terraform init
terraform plan

# Build infra
terraform deploy

# Get region and cluster name variables from tf output
aws eks --region $(terraform output -raw region) update-kubeconfig \
    --name $(terraform output -raw cluster_name)

# verify cluster config
kubectl cluster-info

# (Re)start Istio Ingress
kubectl rollout restart deployment istio-ingress -n istio-ingress

# ECR authentication
aws ecr get-login-password --region $(terraform output -raw region) | docker login --username AWS --password-stdin $(terraform output -raw canine_glucose_ecr_url | cut -d/ -f1)
