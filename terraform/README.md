# Terraform — Phase 2 (Cloud Deployment)

Infrastructure as code for AWS deployment.

See [PHASE2_CLOUD_DEPLOYMENT.md](../PHASE2_CLOUD_DEPLOYMENT.md) and [README.md](../README.md#phase-2-cloud-deployment).

## Quick start

```bash
cd terraform
terraform init
terraform plan -var="opencellid_api_key=pk.YOUR_TOKEN"
terraform apply -var="opencellid_api_key=pk.YOUR_TOKEN"
```

Optional: clone repo onto EC2 at bootstrap:

```bash
terraform apply -var="opencellid_api_key=pk.xxx" -var="git_repo_url=https://github.com/you/netpulse.git"
```

## Default region

`ap-southeast-2` (Sydney). Override with `-var="aws_region=ap-southeast-1"`.

## Outputs

After apply, capture `rds_endpoint`, `s3_bucket_name`, `ec2_instance_id`, and SSM port-forward commands.

## Teardown

```bash
terraform destroy -var="opencellid_api_key=pk.xxx"
```

S3 bucket has `prevent_destroy` — remove that lifecycle block first if you need to delete the bucket.
