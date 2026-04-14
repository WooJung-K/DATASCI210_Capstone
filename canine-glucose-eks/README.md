
# Cluster Initialization

### Provision Infrastructure
`terraform init`
`terraform plan`
`terraform apply`

### Update  kubectl context
#### get region and cluster name variables from tf output
`aws eks --region $(terraform output -raw region) update-kubeconfig --name $(terraform output -raw cluster_name)`

# verify cluster config
kubectl cluster-info

### Restart Istio Ingress (figure out how to fix this bug)
`kubectl rollout restart deployment istio-ingress -n istio-ingress`

# Deployment
Switch to deploymet directory and run `build-push.sh`

# Cluster Destruction

The AWS Load Balancer Controller add-on asynchronously reconciles resource deletions.
During stack destruction, the istio ingress resource and the load balancer controller
add-on are deleted in quick succession, preventing the removal of some of the AWS
resources associated with the ingress gateway load balancer like, the frontend and the
backend security groups.
This causes the final `terraform destroy -auto-approve` command to timeout and fail with VPC dependency errors like below:

```text
│ Error: deleting EC2 VPC (vpc-XXXX): operation error EC2: DeleteVpc, https response error StatusCode: 400, RequestID: XXXXX-XXXX-XXXX-XXXX-XXXXXX, api error DependencyViolation: The vpc 'vpc-XXXX' has dependencies and cannot be deleted.
```

A possible workaround is to manually uninstall the `istio-ingress` helm chart.

```sh
terraform destroy -target='module.eks_blueprints_addons.helm_release.this["istio-ingress"]' -auto-approve
```

Once the chart is uninstalled move on to destroy the stack.

{%
   include-markdown "../../docs/_partials/destroy.md"
%}