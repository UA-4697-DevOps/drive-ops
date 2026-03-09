# ==============================================================================
# ROUTE53 MODULE – HOSTED ZONE
# ==============================================================================

resource "aws_route53_zone" "main" {
  name = var.domain_name

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.env}-hosted-zone"
    }
  )
}
