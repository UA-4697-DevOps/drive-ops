include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "../../../../terraform/modules/sqs"
}

dependency "sqs_driver_assigned_dlq" {
  config_path = "../sqs-driver-assigned-dlq"
}

inputs = {
  queue_name           = "dev-driver-assigned" # Added environment discriminator
  visibility_timeout   = 30
  max_receive_count    = 3
  dead_letter_queue_arn = dependency.sqs_driver_assigned_dlq.outputs.dlq_arn

  tags = {
    Component = "sqs-driver-assigned"
    EventType = "trip.event.driver_assigned"
  }
}
