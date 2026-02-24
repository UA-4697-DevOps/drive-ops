# CHANGELOG

## [Unreleased]

### Breaking Change
- The default for `cluster_endpoint_public_access` is now `false` (was `true`). This means new clusters will have a private-only API endpoint by default. If you require public access, set `cluster_endpoint_public_access = true` and specify trusted CIDRs in `cluster_endpoint_public_access_cidrs`.

**Migration:**
- Existing callers relying on public endpoint access must explicitly set `cluster_endpoint_public_access = true` in their configuration to avoid losing public API access after upgrading this module.
- **Warning:** Upgrading without setting `cluster_endpoint_public_access = true` will cause operator lockout if no private connectivity (VPN/Direct Connect/bastion/VPC peering) exists. Ensure `cluster_endpoint_public_access_cidrs` is set alongside `cluster_endpoint_public_access` to explicitly allow the desired public CIDRs.

---
