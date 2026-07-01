# Terraform — Phase 2 (Cloud Deployment)

Infrastructure as code for AWS deployment.

See [PHASE2_CLOUD_DEPLOYMENT.md](../PHASE2_CLOUD_DEPLOYMENT.md) and [README.md](../README.md#phase-2-cloud-deployment).

## Quick start

```bash
cd terraform
terraform init
terraform plan
terraform apply
```

Optional: clone repo onto EC2 at bootstrap:

```bash
terraform apply -var="git_repo_url=https://github.com/you/netpulse.git"
```

Set `OPENCELLID_API_KEY` in `/opt/netpulse/.env.cloud` on EC2 before running DAG 0 (not in Terraform).

## Default region

`ap-southeast-2` (Sydney). Override with `-var="aws_region=ap-southeast-1"`.

## Outputs

After apply, capture `rds_endpoint`, `s3_bucket_name`, `ec2_instance_id`, and SSM port-forward commands.

## Teardown

```bash
terraform destroy
```

S3 bucket has `prevent_destroy` — remove that lifecycle block first if you need to delete the bucket.
