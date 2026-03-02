include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "../../../../terraform/modules/sqs"
}

inputs = {
  queue_name         = "driver-assigned"
  visibility_timeout = 30
  max_receive_count  = 3

  tags = {
    Component = "sqs-driver-assigned"
    EventType = "trip.event.driver_assigned"
  }
}
