# AWS Skill

Interact with Amazon Web Services for EC2, ECS, Lambda, CloudWatch, RDS, and S3 operations.

## Configuration

```yaml
aws:
  access_key: ${AWS_ACCESS_KEY_ID}      # Optional if using default credential chain
  secret_key: ${AWS_SECRET_ACCESS_KEY}  # Optional if using default credential chain
  region: us-east-1                     # Default region
  profile: default                       # Optional AWS profile
  assume_role_arn: arn:aws:iam::...     # Optional role to assume
```

## Actions

### EC2 Operations
| Action | Description | Parameters |
|--------|-------------|------------|
| `ec2_list_instances` | List EC2 instances | `region`, `filters` |
| `ec2_get_instance` | Get instance details | `instance_id` |
| `ec2_start_instance` | Start an instance | `instance_id` |
| `ec2_stop_instance` | Stop an instance | `instance_id` |

### ECS Operations
| Action | Description | Parameters |
|--------|-------------|------------|
| `ecs_list_services` | List ECS services | `cluster` |
| `ecs_update_service` | Update service config | `cluster`, `service`, `desired_count` |

### Lambda Operations
| Action | Description | Parameters |
|--------|-------------|------------|
| `lambda_invoke` | Invoke a Lambda function | `function_name`, `payload` |

### CloudWatch Operations
| Action | Description | Parameters |
|--------|-------------|------------|
| `cloudwatch_get_metrics` | Query metrics | `namespace`, `metric_name`, `dimensions` |
| `cloudwatch_get_alarms` | List alarms | `state_filter` |

### RDS Operations
| Action | Description | Parameters |
|--------|-------------|------------|
| `rds_describe_instances` | List RDS instances | `filters` |

### S3 Operations
| Action | Description | Parameters |
|--------|-------------|------------|
| `s3_list_buckets` | List S3 buckets | |

## Authentication

Uses the standard AWS credential chain:
1. Environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)
2. AWS credentials file (`~/.aws/credentials`)
3. IAM role (when running on EC2/Lambda/ECS)
4. Instance profile

## Example Usage

```python
# List EC2 instances with a specific tag
result = await aws.ec2_list_instances(
    filters=[{"Name": "tag:Environment", "Values": ["production"]}]
)

# Get CloudWatch metrics
result = await aws.cloudwatch_get_metrics(
    namespace="AWS/EC2",
    metric_name="CPUUtilization",
    dimensions={"InstanceId": "i-1234567890abcdef0"}
)
```
