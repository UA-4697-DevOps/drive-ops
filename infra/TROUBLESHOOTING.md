# 🛠 Debugging Networking with VPC Flow Logs

VPC Flow Logs are enabled in the `dev` environment to help diagnose connectivity issues (e.g., failed connections to RDS, blocked webhooks, or unreachable services).

**Log Group:** `/aws/vpc-flow-log/drive-ops-dev`
**Retention:** 3 Days (Data older than 3 days is automatically deleted to save costs).

## 🔍 How to Analyze Logs

1. Go to the **AWS Console** -> **CloudWatch** -> **Logs Insights**.
2. Select the log group: `/aws/vpc-flow-log/drive-ops-dev`.
3. Paste one of the queries below and click **Run query**.

---

## ⚡️ Useful CloudWatch Insights Queries

### 1. Find Blocked Traffic (Security Group Rejects)
*Use this to see who is trying to connect but getting blocked by Security Groups or NACLs.*

```sql
fields @timestamp, interfaceId, srcAddr, dstAddr, dstPort, protocol
| filter action="REJECT"
| sort @timestamp desc
| limit 20
```

### 2. Debug RDS Connectivity (Port 5432)
*Check if application servers or other services can reach the PostgreSQL database.*

```sql
fields @timestamp, srcAddr, dstAddr, action, logStatus
| filter dstPort=5432
| sort @timestamp desc
| limit 20
```

### 3. Analyze Top Traffic Sources
*See which IP addresses are sending the most data (useful for identifying anomalies or spam).*

```sql
fields srcAddr, dstAddr, bytes
| stats sum(bytes) as totalBytes by srcAddr
| sort totalBytes desc
| limit 10
```

### 4. Filter by Specific IP
*Replace 10.0.0.123 with the IP you are debugging.*

```sql
fields @timestamp, action, srcAddr, dstAddr, dstPort
| filter srcAddr="10.0.0.123" or dstAddr="10.0.0.123"
| sort @timestamp desc
| limit 50
```
