# Customer Backup Policy

Mission Control stores backup confirmation metadata, not customer backup payloads.

## Ownership Model

- Backups are customer-owned.
- Customers choose destination (local drive, external drive, customer cloud, or manual export).
- Mission Control tracks only policy metadata:
  - confirmation status,
  - selected destination type/label,
  - reminder timestamps.

## Reminder Cadence

- Reminder cadence is twice weekly.
- If backups are unconfirmed, reminder responses must include a clear warning:
  - skipping backups can result in total data loss.

## Confirmation Workflow

- Owner confirms backup intent through backup API workflow.
- Destination type is required when backup intent is affirmative.
- Metadata records whether backup is confirmed or declined.
- No customer file contents are uploaded or retained by this workflow.

## Recommended Operator Script

Weekly operator review:

1. Query tenants with unconfirmed backup policy.
2. Send reminder to owner channel (Telegram/WhatsApp/UI surface).
3. Record confirmation status and destination metadata.
4. Escalate repeated declines to account-management review.
