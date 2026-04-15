output "cluster_endpoint" {
  description = "Endpoint for EKS control plane"
  value       = module.eks.cluster_endpoint
}

output "cluster_security_group_id" {
  description = "Security group ids attached to the cluster control plane"
  value       = module.eks.cluster_security_group_id
}

output "region" {
  description = "AWS region"
  value       = var.region
}

output "cluster_name" {
  description = "Kubernetes Cluster Name"
  value       = module.eks.cluster_name
}

output "configure_kubectl" {
  description = "Configure kubectl: make sure you're logged in with the correct AWS profile and run the following command to update your kubeconfig"
  value       = "aws eks --region ${var.region} update-kubeconfig --name ${module.eks.cluster_name}"
}

output "canine_glucose_ecr_url" {
  value = aws_ecr_repository.canine_glucose_ecr.repository_url
}

output "cloudfront_distribution_domain_name" {
  value = try(aws_cloudfront_distribution.canine_glucose_api[0].domain_name, null)
}

output "cloudfront_distribution_url" {
  value = try("https://${aws_cloudfront_distribution.canine_glucose_api[0].domain_name}", null)
}