include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "../../../../terraform/modules/sqs"
}

inputs = {
  queue_name         = "trip-completed"
  visibility_timeout = 30
  max_receive_count  = 3

  tags = {
    Component = "sqs-trip-completed"
    EventType = "trip.event.completed"
  }
}
