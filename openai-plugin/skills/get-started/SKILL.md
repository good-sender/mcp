---
name: get-started
description: Set up GoodSender after installing it. Checks the connected workspace's blog, sender domains and sender identities, explains what is still missing before posts can be published or email sent, and suggests a first step.
---

# Get started with GoodSender

Use this skill right after the user connects GoodSender, or when they ask what they can do with it.

1. Call `get_blog` to read the workspace's blog settings. If the blog has no title or description, offer to set them with `update_blog` (ask before running it: it changes the public site).
2. Call `list_sender_identities` and `check_sender_domain_stats`. Tell the user whether they have a verified sender domain and a sender identity. Without one, they can publish to the blog but cannot send email or newsletters; point them to the GoodSender dashboard to verify a domain.
3. Call `list_posts` and summarize how many posts are published and how many are drafts.
4. Suggest one next step that fits what you found, for example:
   - "Draft a post from these notes and show me a preview before publishing."
   - "Email my latest post to newsletter subscribers."
   - "Send the 'Weekly update' template to my beta-users group."

Ground rules:

- Never publish, send, delete or change the live site without the user's explicit go-ahead. Show a preview first (`create_post_preview`, `render_template_preview`).
- GoodSender only emails recipients who opted in. Adding a recipient sends them a consent request; mail to them waits until they consent. Do not offer to work around consent.
- Transactional templates (`send_consentless_email`) are for messages the recipient asked for, such as one-time codes and receipts, sent from the workspace's own verified domain.
