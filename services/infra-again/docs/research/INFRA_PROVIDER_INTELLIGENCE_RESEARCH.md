# Infrastructure Provider Intelligence Research

**Date:** 2026-08-09
**Status:** Research — Phase 0/1

## Purpose

Identify official machine-readable sources for provider capability data.
The Dynamic Capability Registry must be populated from OFFICIAL sources,
not LLM memory.

## AWS Provider Sources

| Source | Type | Description | Status |
|---|---|---|---|
| CloudFormation Registry | OFFICIAL | Resource type schemas (JSON) | Research |
| Cloud Control API | OFFICIAL | CRUDL operations for resources | Research |
| AWS Price List API | OFFICIAL | Bulk pricing data (JSON/CSV) | Research |
| AWS SDK (boto3) | OFFICIAL | Service/API discovery | Research |
| AWS Regions/Endpoints | OFFICIAL | Region availability metadata | Research |
| Terraform AWS Provider | THIRD_PARTY | Resource/provider schemas | Research |
| CloudFormation Resource Specification | OFFICIAL | Resource property schemas | Research |

### Key Findings
- CloudFormation Registry provides machine-readable JSON schemas for all AWS resource types
- Cloud Control API provides standardized CRUDL across services
- Pricing API offers bulk JSON/CSV downloads with service/region/term granularity
- boto3 service model provides API version and endpoint data

### Provenance
- CloudFormation: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/resource-type-schemas.html
- Cloud Control: https://docs.aws.amazon.com/cloudcontrolapi/latest/userguide/
- Pricing: https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/price-list-api.html

## GCP Provider Sources

| Source | Type | Description | Status |
|---|---|---|---|
| Service Usage API | OFFICIAL | Available services enumeration | Research |
| Cloud Asset Inventory | OFFICIAL | Resource metadata/search | Research |
| Cloud Billing API | OFFICIAL | Pricing/catalog metadata | Research |
| GCP SDK (google-cloud-*) | OFFICIAL | Service/API discovery | Research |
| Terraform Google Provider | THIRD_PARTY | Resource/provider schemas | Research |
| GCP Discovery API | OFFICIAL | API discovery document | Research |

### Key Findings
- Service Usage API lists enabled services per project
- Cloud Asset Inventory provides resource search and metadata
- Cloud Billing Catalog API provides SKU/pricing data
- GCP APIs publish Google Discovery format documents

### Provenance
- Service Usage: https://cloud.google.com/service-usage/docs
- Cloud Asset: https://cloud.google.com/asset-inventory/docs
- Billing: https://cloud.google.com/billing/docs

## On-Prem Sources

| Source | Type | Description | Status |
|---|---|---|---|
| Manual Registration | — | User-registered resources | Design |
| Discovery Agents | — | Network-scanned resources | Future |
| CMDB Integration | THIRD_PARTY | Existing inventory systems | Future |

## Classification

All sources must be classified:

```
OFFICIAL_SOURCE — Direct from provider (AWS API, GCP API)
THIRD_PARTY_SOURCE — Community/partner maintained
SIMULATOR — Emulation, not real provider
LOCAL_RUNTIME — Real software running locally
REAL_PROVIDER — Actual cloud provider connection
```

## Catalog Synchronization Design

```
Official Provider API
        ↓
Catalog Synchronizer (per-provider)
        ↓
Raw Provider Metadata (versioned, checksummed)
        ↓
Normalization Layer (provider-agnostic schema)
        ↓
Dynamic Capability Registry
```

### Version Tracking
Every sync produces a CatalogSnapshot with:
- Provider identifier
- Source API version
- Collection timestamp
- Content checksum
- Diff from previous version

### Change Detection
Compare consecutive snapshots:
- New resources added
- Resources deprecated
- Schema/property changes
- Pricing changes
- Region availability changes
