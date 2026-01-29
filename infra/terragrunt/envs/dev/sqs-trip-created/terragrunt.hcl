include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "../../../../terraform/modules/sqs"
}

inputs = {
  queue_name         = "trip-created"
  visibility_timeout = 60
  max_receive_count  = 3

  tags = {
    Component = "sqs-trip-created"
    EventType = "trip.event.created"
  }
}
