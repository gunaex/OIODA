# AWS Provider Source Research

**Date:** 2026-08-09

## Official Machine-Readable Sources

### 1. CloudFormation Resource Registry
- **URL:** https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/resource-type-schemas.html
- **Format:** JSON Schema (draft-07)
- **Coverage:** All AWS CloudFormation resource types
- **Update cadence:** Per-service releases
- **Provenance:** Official AWS

### 2. Cloud Control API
- **URL:** https://docs.aws.amazon.com/cloudcontrolapi/latest/userguide/
- **Capabilities:** List resource types, get type schema, CRUDL operations
- **Format:** JSON
- **Use:** Dynamic resource discovery + standardized operations

### 3. AWS Price List API
- **URL:** https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/price-list-api.html
- **Format:** JSON (bulk), CSV
- **Granularity:** Service → Region → Term → SKU
- **Use:** Cost estimation without hardcoding

### 4. AWS SDK (boto3)
- **URL:** https://boto3.amazonaws.com/v1/documentation/api/latest/index.html
- **Capabilities:** Service models, API versions, endpoint data
- **Use:** Runtime provider interaction (when connected)

### 5. Terraform AWS Provider Schema
- **URL:** https://registry.terraform.io/providers/hashicorp/aws/
- **Type:** THIRD_PARTY (HashiCorp-maintained)
- **Use:** IaC resource type reference

## For INFRA-AGAIN

Phase 2+ should implement:
1. `AwsCatalogSynchronizer` using CloudFormation Registry + Cloud Control API
2. `AwsPricingCollector` using Price List API
3. Provider-neutral mapping from CloudFormation types to capability categories

Phase 1: Minimal curated mapping in `AwsProviderAdapter` — clearly marked as not authoritative.
