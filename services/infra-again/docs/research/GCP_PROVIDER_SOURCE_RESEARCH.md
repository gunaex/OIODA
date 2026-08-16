# GCP Provider Source Research

**Date:** 2026-08-09

## Official Machine-Readable Sources

### 1. Service Usage API
- **URL:** https://cloud.google.com/service-usage/docs
- **Capabilities:** List enabled services, service metadata
- **Format:** JSON (REST/gRPC)

### 2. Cloud Asset Inventory
- **URL:** https://cloud.google.com/asset-inventory/docs
- **Capabilities:** Resource search, metadata, IAM analysis
- **Format:** JSON

### 3. Cloud Billing Catalog API
- **URL:** https://cloud.google.com/billing/docs
- **Capabilities:** SKU listing, pricing metadata
- **Format:** JSON

### 4. Google Discovery API
- **URL:** https://developers.google.com/discovery
- **Capabilities:** API discovery documents for all GCP services
- **Format:** JSON (Google Discovery format)

### 5. Terraform Google Provider Schema
- **URL:** https://registry.terraform.io/providers/hashicorp/google/
- **Type:** THIRD_PARTY

## GCP Emulators

- Pub/Sub emulator (official)
- Firestore emulator (official)
- Spanner emulator (official)
- Bigtable emulator (official)
- Datastore emulator (official)
- fake-gcs-server (third-party, fsouza)

## For INFRA-AGAIN

Phase 2+ should implement:
1. `GcpCatalogSynchronizer` using Service Usage + Discovery API
2. `GcpPricingCollector` using Cloud Billing Catalog API
3. Provider-neutral mapping from GCP service types to capability categories
