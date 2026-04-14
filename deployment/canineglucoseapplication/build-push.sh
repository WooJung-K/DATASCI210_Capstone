#!/usr/bin/env bash
set -euo pipefail

# Relative File Path Variables
TF_DIR='../../canine-glucose-eks'
REGION="$(terraform -chdir="$TF_DIR" output -raw region)"
CLUSTER_NAME="$(terraform -chdir="$TF_DIR" output -raw cluster_name)"
ECR_DOMAIN="$(terraform -chdir="$TF_DIR" output -raw canine_glucose_ecr_url)"


### Get latest git hash, and update the tag in prod-kustomize
export TAG=$(git rev-parse --short HEAD)
export ECR_DOMAIN="$(terraform -chdir="$TF_DIR" output -raw canine_glucose_ecr_url)"
yq -i '
  (.images[] | select(.name == "app").newName) = strenv(ECR_DOMAIN) |
  (.images[] | select(.name == "app").newTag) = strenv(TAG)
' .k8s/overlays/prod/kustomization.yaml


# Initialize Minikube
minikube start --kubernetes-version=v1.34
kubectl config set-context --current --namespace=cgi-prod


### Make python available to environment so poetry can build the image
eval "$("$HOME/anaconda3/bin/conda" shell.bash hook)"
conda activate w210

### Change to EKS Context
aws eks --region "$REGION" update-kubeconfig --name "$CLUSTER_NAME"

### ECR Login
aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$(echo "$ECR_DOMAIN" | cut -d/ -f1)"


# Push to AWS ECR
### Build image locally with minikube, assign latest git hash as tag
eval $(minikube docker-env)
docker build --platform linux/amd64 -t app:"$TAG" .
docker tag app:"$TAG" "${ECR_DOMAIN}:${TAG}"
docker push "${ECR_DOMAIN}:${TAG}"
docker pull "${ECR_DOMAIN}:${TAG}"


# # Update git repo to use the tagged image version
# git add .k8s/overlays/prod/
# git commit -m "(Automated) Update k8 prod overlay to use image version: ${TAG}"


# Deploy new image in prod
kubectl apply -k .k8s/overlays/prod/


ELB=$(kubectl get svc istio-ingress -n istio-ingress -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')

echo 'App url: '
echo http://$ELB/woof/docs
