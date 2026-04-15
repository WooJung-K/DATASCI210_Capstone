##### Providers #####
# Terraform providers are plugins that allow interactions with some external API or service.
# Adds a set of resource types and/or data sources that terraform can manage.
# When declared here, terraform pulls the plugin from the terraform registry.


# Cloud Service Provider we will use
provider "aws" {
  region = var.region
}

provider "kubernetes" {
  host                   = module.eks.cluster_endpoint
  cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)

  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    command     = "aws"
    # This requires the awscli to be installed locally where Terraform is executed
    args = ["eks", "get-token", "--cluster-name", module.eks.cluster_name]
  }
}

provider "helm" {
  kubernetes {
    host                   = module.eks.cluster_endpoint
    cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)

    exec {
      api_version = "client.authentication.k8s.io/v1beta1"
      command     = "aws"
      # This requires the awscli to be installed locally where Terraform is executed
      args = ["eks", "get-token", "--cluster-name", module.eks.cluster_name]
    }
  }
}


##### Data #####
# Data blocks fetch data about a resource from the provider, without provisioning the infrastructure object.


# Filter out local zones, which are not currently supported 
# with managed node groups
data "aws_availability_zones" "available" {
  filter {
    name   = "opt-in-status"
    values = ["opt-in-not-required"]
  }
}


data "aws_iam_policy" "ebs_csi_policy" {
  arn = "arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy"
}


data "kubernetes_service" "istio_ingress" {
  metadata {
    name      = "istio-ingress"
    namespace = "istio-ingress"
  }

  depends_on = [
    module.eks_blueprints_addons
  ]
}

##### IAM #####

module "irsa-ebs-csi" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-assumable-role-with-oidc"
  version = "5.39.0"

  create_role                   = true
  role_name                     = "AmazonEKSTFEBSCSIRole-${module.eks.cluster_name}"
  provider_url                  = module.eks.oidc_provider
  role_policy_arns              = [data.aws_iam_policy.ebs_csi_policy.arn]
  oidc_fully_qualified_subjects = ["system:serviceaccount:kube-system:ebs-csi-controller-sa"]
}

################################################################################
# VPC
################################################################################

# Create VPC for cluster
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "5.8.1"

  name = "k8-vpc"

  cidr = "10.0.0.0/16"
  azs  = slice(data.aws_availability_zones.available.names, 0, 3)
  
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  public_subnets  = ["10.0.4.0/24", "10.0.5.0/24", "10.0.6.0/24"]

  enable_nat_gateway   = true
  single_nat_gateway   = true
  enable_dns_hostnames = true

  public_subnet_tags = {
    "kubernetes.io/role/elb" = 1
  }

  private_subnet_tags = {
    "kubernetes.io/role/internal-elb" = 1
  }
}


################################################################################
# Create EKS Cluster
################################################################################

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.11" # version of eks terraform module

# name and k8 version 
  cluster_name               = "canine-glucose-eks"
  cluster_version = "1.34"

# is cluster open to the internet? does the IAM user creating the cluster have admin permissions?
  cluster_endpoint_public_access           = true
  enable_cluster_creator_admin_permissions = true

  cluster_addons = {
    aws-ebs-csi-driver = {
      service_account_role_arn = module.irsa-ebs-csi.iam_role_arn
    }
    coredns    = {}
    kube-proxy = {}
    vpc-cni    = {}
  }

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  eks_managed_node_group_defaults = {
    iam_role_additional_policies = {
      ecr_read_only = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
    }
  }

  eks_managed_node_groups = {
    initial = {
      name = "node-group-1"

      instance_types = ["m5.large"]

      min_size     = 1
      max_size     = 3
      desired_size = 2
    }
  }

  #  EKS K8s API cluster needs to be able to talk with the EKS worker nodes with port 15017/TCP and 15012/TCP which is used by Istio
  #  Istio in order to create sidecar needs to be able to communicate with webhook and for that network passage to EKS is needed.
  node_security_group_additional_rules = {
    ingress_15017 = {
      description                   = "Cluster API - Istio Webhook namespace.sidecar-injector.istio.io"
      protocol                      = "TCP"
      from_port                     = 15017
      to_port                       = 15017
      type                          = "ingress"
      source_cluster_security_group = true
    }
    ingress_15012 = {
      description                   = "Cluster API to nodes ports/protocols"
      protocol                      = "TCP"
      from_port                     = 15012
      to_port                       = 15012
      type                          = "ingress"
      source_cluster_security_group = true
    }
  }
}

resource "kubernetes_namespace_v1" "dev" {
  metadata {
    name = "cgi-dev"

    labels = {
      istio-injection = "enabled"
      env             = "cgi-dev"
    }
  }
}

resource "kubernetes_namespace_v1" "prod" {
  metadata {
    name = "cgi-prod"

    labels = {
      istio-injection = "enabled"
      env             = "cgi-prod"
    }
  }
}

################################################################################
# EKS Addons (Istio, Cluster Autoscaler)
################################################################################

resource "kubernetes_namespace_v1" "istio_system" {
  metadata {
    name = "istio-system"
  }
}

module "eks_blueprints_addons" {
  source  = "aws-ia/eks-blueprints-addons/aws"
  version = "~> 1.23"

  cluster_name      = module.eks.cluster_name
  cluster_endpoint  = module.eks.cluster_endpoint
  cluster_version   = module.eks.cluster_version
  oidc_provider_arn = module.eks.oidc_provider_arn

  # Core addons
  enable_aws_load_balancer_controller = true
  enable_metrics_server               = true
  enable_kube_prometheus_stack        = true

  enable_cluster_autoscaler = true
  cluster_autoscaler = {

    namespace = "kube-system"

    values = [
      yamlencode({
        autoDiscovery = {
          clusterName = module.eks.cluster_name
        }

        awsRegion = var.region

        extraArgs = {
          balance-similar-node-groups = "true"
          skip-nodes-with-local-storage = "false"
        }
      })
    ]
  }


  helm_releases = {

    istio-base = {
      chart         = "base"
      chart_version = var.istio_chart_version
      repository    = var.istio_chart_url
      name          = "istio-base"
      namespace     = kubernetes_namespace_v1.istio_system.metadata[0].name

      wait = true
    }

    istiod = {
      chart         = "istiod"
      chart_version = var.istio_chart_version
      repository    = var.istio_chart_url
      name          = "istiod"
      namespace     = kubernetes_namespace_v1.istio_system.metadata[0].name

      wait = true

      set = [
        {
          name  = "meshConfig.accessLogFile"
          value = "/dev/stdout"
        }
      ]
    }

    istio-ingress = {
      chart            = "gateway"
      chart_version    = var.istio_chart_version
      repository       = var.istio_chart_url
      name             = "istio-ingress"
      namespace        = "istio-ingress" # per https://github.com/istio/istio/blob/master/manifests/charts/gateways/istio-ingress/values.yaml#L2
      create_namespace = true
      
      wait = true

      values = [
        yamlencode(
          {
            labels = {
              istio = "ingressgateway"
            }
            service = {
              annotations = {
                "service.beta.kubernetes.io/aws-load-balancer-type"            = "external"
                "service.beta.kubernetes.io/aws-load-balancer-nlb-target-type" = "ip"
                "service.beta.kubernetes.io/aws-load-balancer-scheme"          = "internet-facing"
                "service.beta.kubernetes.io/aws-load-balancer-attributes"      = "load_balancing.cross_zone.enabled=true"
              }
            }
          }
        )
      ]
    }
  }
}


################################################################################
# EKS Addons (Cluster Autoscaler Kubernetes Permissions)
################################################################################

resource "kubernetes_cluster_role_v1" "cluster_autoscaler_volumeattachments" {
  metadata {
    name = "cluster-autoscaler-volumeattachments"
  }

  rule {
    api_groups = ["storage.k8s.io"]
    resources  = ["volumeattachments"]
    verbs      = ["get", "list", "watch"]
  }
}

resource "kubernetes_cluster_role_binding_v1" "cluster_autoscaler_volumeattachments" {
  metadata {
    name = "cluster-autoscaler-volumeattachments"
  }

  role_ref {
    api_group = "rbac.authorization.k8s.io"
    kind      = "ClusterRole"
    name      = kubernetes_cluster_role_v1.cluster_autoscaler_volumeattachments.metadata[0].name
  }

  subject {
    kind      = "ServiceAccount"
    name      = "cluster-autoscaler-sa"
    namespace = "kube-system"
  }
}


################################################################################
# EKS Addons (ECR - Elastic Container)
################################################################################

resource "aws_ecr_repository" "canine_glucose_ecr" {
  name = "canine-glucose-ecr"
  image_tag_mutability = "IMMUTABLE"
  image_scanning_configuration { scan_on_push = true }
}


################################################################################
# EKS Addons (Cloudfront Domain Registration)
################################################################################


resource "aws_cloudfront_distribution" "canine_glucose_api" {
  count = var.cloudfront_enabled ? 1 : 0

  enabled         = true
  is_ipv6_enabled = true
  comment         = "CloudFront for canine glucose API"

  origin {
    domain_name = data.kubernetes_service.istio_ingress.status[0].load_balancer[0].ingress[0].hostname
    origin_id   = "canine-glucose-elb"

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "http-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  default_cache_behavior {
    target_origin_id       = "canine-glucose-elb"
    viewer_protocol_policy = "redirect-to-https"
    compress               = true

    allowed_methods = ["GET", "HEAD", "OPTIONS", "PUT", "PATCH", "POST", "DELETE"]

    cached_methods = [
      "GET",
      "HEAD",
      "OPTIONS",
    ]

    # AWS managed: CachingDisabled
    cache_policy_id = "4135ea2d-6df8-44a3-9df3-4b5a84be39ad"

    # AWS managed: AllViewerExceptHostHeader
    # Forwards all viewer headers/cookies/query strings except Host.
    origin_request_policy_id = "b689b0a8-53d0-40ab-baf2-68738e2966ac"

    # AWS managed: CORS-With-Preflight
    response_headers_policy_id = "5cc3b908-e619-4b99-88e5-2cf7f45965bd"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  price_class = var.cloudfront_price_class
}