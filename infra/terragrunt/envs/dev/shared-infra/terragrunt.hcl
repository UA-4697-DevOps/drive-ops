include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  # Points to the module logic you created earlier
  source = "../../../../terraform/modules/vpc"
}

inputs = {
  # This follows the "minimal, secure dev environment" requirement
  vpc_cidr = "10.0.0.0/16"
}
