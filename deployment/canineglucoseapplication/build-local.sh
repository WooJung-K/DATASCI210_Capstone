#!/usr/bin/env bash
set -euo pipefail

# Initialize Minikube 
minikube start --kubernetes-version=v1.34
kubectl create namespace cgi-local # canine glucose inference
kubectl config set-context --current --namespace=cgi-local
kubectl config use-context minikube

# Configure Minikube
### Make python available to environment so poetry can build the image
eval "$("$HOME/anaconda3/bin/conda" shell.bash hook)"
conda activate w210

### Set current session to use minikube's docker daemon
eval $(minikube docker-env)

# Build Image in minikube
docker build -t app:latest .

# Start application locally via Kustomize
kubectl apply -k .k8s/overlays/dev/