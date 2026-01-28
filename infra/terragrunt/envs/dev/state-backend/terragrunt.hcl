include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "../../../../terraform/modules/state-backend"
}

inputs = {
  state_bucket_name = "drive-ops-dev-terraform-state"
  lock_table_name   = "drive-ops-dev-terraform-locks"
  
  tags = {
    Component = "state-backend"
  }
}
