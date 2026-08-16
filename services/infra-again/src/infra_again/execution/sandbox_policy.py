"""
Phase 8.1B — Least-privilege IAM policy for INFRA-AGAIN S3 Sandbox acceptance.

READ-ONLY: This is a policy artifact/document. IAM mutation is FORBIDDEN.
Use this as a reference when configuring sandbox credentials.

Do NOT attach inline. Do NOT create roles automatically.
"""

LEAST_PRIVILEGE_S3_SANDBOX_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "StsGetCallerIdentity",
            "Effect": "Allow",
            "Action": ["sts:GetCallerIdentity"],
            "Resource": ["*"],
        },
        {
            "Sid": "S3SandboxBucketLifecycle",
            "Effect": "Allow",
            "Action": [
                "s3:CreateBucket",
                "s3:DeleteBucket",
                "s3:GetBucketLocation",
                "s3:PutBucketPublicAccessBlock",
                "s3:GetBucketPublicAccessBlock",
                "s3:PutBucketTagging",
                "s3:GetBucketTagging",
                "s3:ListBucket",
                "s3:HeadBucket",
            ],
            "Resource": ["arn:aws:s3:::infra-again-sandbox-*"],
        },
    ],
}

# Human-readable summary
REQUIRED_PERMISSIONS = [
    "sts:GetCallerIdentity",
    "s3:CreateBucket",
    "s3:DeleteBucket",
    "s3:GetBucketLocation",
    "s3:PutBucketPublicAccessBlock",
    "s3:GetBucketPublicAccessBlock",
    "s3:PutBucketTagging",
    "s3:GetBucketTagging",
    "s3:ListBucket",
    "s3:HeadBucket",
]

# Credential bootstrap guide
CREDENTIAL_BOOTSTRAP_GUIDE = """
Recommended credential sources (in order of preference):

1. AWS IAM Identity Center (SSO)
   aws sso login --profile infra-again-sandbox
   export AWS_PROFILE=infra-again-sandbox

2. Temporary STS credentials
   Use get-session-token or assume-role for short-lived creds
   export AWS_ACCESS_KEY_ID=...
   export AWS_SECRET_ACCESS_KEY=...
   export AWS_SESSION_TOKEN=...

3. Named sandbox profile (least preferred for long-lived keys)
   [profile infra-again-sandbox]
   region = us-east-1

NEVER use:
- Production AWS accounts
- Root account credentials
- Long-lived IAM user access keys without MFA
- Credentials with broad * permissions
"""


def generate_policy_document() -> dict:
    """Return the recommended least-privilege policy for S3 sandbox acceptance."""
    return LEAST_PRIVILEGE_S3_SANDBOX_POLICY


def get_required_permissions() -> list[str]:
    """Return the list of required permissions for S3 sandbox acceptance."""
    return REQUIRED_PERMISSIONS
