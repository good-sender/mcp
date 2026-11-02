# GoodSender for Gemini CLI

GoodSender publishes blog posts and sends newsletters and email through the hosted MCP server
at https://mcp.goodsender.com/. You sign in with your GoodSender account in the browser the
first time a tool runs (`/mcp auth goodsender` to sign in again).

## Before you act

- Create posts as drafts first (`create_post`); never publish in the same step.
- Show the preview (`create_post_preview`) and the distribution plan (`get_post_distribution`)
  and ask the user to confirm before `publish_post`, `broadcast_post` or `reannounce_post`.
- Ask the user to confirm before any `enqueue_*` or `send_*` email tool and before any
  `delete_*` tool. The hosted server has no `confirm_action`: Gemini CLI's own tool
  confirmation prompt is the approval step, so never bypass or pre-answer it.

## Email

- Custom emails to recipients who have not consented are queued until they consent;
  `send_pending_emails` sends the queue. Only the built-in transactional templates
  (`send_consentless_email`: OTP, MFA, login, password/email change, receipts) send right away.
- Cold outreach is not supported; do not add recipients who did not ask to hear from the user.

## Never

- Claim a capability a tool does not offer; if a tool returns an error, show it and stop.
- Invent DNS records, domain status or send results — read them from the tools.
