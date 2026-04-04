# CloudWatch Log Group Shared Module

Generic reusable module for managing AWS CloudWatch Log Groups via `for_each`.

Applies to: vpc (flow logs), eks (control plane logs), tag-auditor (lambda logs), monitoring (service logs).

## Usage
```hcl
module "cloudwatch_log_group" {
  source = "../cloudwatch-log-group"

  log_groups = {
    eks_control_plane = {
      name              = "/aws/eks/drive-ops/cluster"
      retention_in_days = 14
    }
    vpc_flow_logs = {
      name = "/aws/vpc/drive-ops/flow-logs"
    }
    tag_auditor = {
      name = "/aws/lambda/tag-auditor"
    }
  }

  retention_days = 7
  tags           = var.tags
}
```
