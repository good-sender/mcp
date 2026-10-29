# GoodSender MCP Server

Publish blog posts, send newsletters and emails from Claude, Claude Code, Codex and ChatGPT.
Send consent-based email and transactional email (OTP and MFA codes), and publish blog posts on your own domain.
Connect to the hosted server with OAuth and nothing to install, or run it locally with an API key.

## What you can do

Ask your assistant things like:

- "Write a post about our new release, publish it on my blog and email it to subscribers."
- "Draft a post from these notes and show me the preview before anything goes live."
- "Connect blog.example.com to my blog and tell me which DNS records to add."
- "Create a custom design for my blog that matches our logo, and show me a preview first."
- "Send a password reset code to user@example.com with the OTP template."
- "Email the March update to the beta-users group."

Posts are always created as drafts. Before publishing, the assistant shows where the post will go (your blog, the newsletter, connected social accounts) and asks you to approve it. See [Action confirmation](#action-confirmation) for how approval works on the hosted and local servers.
The newsletter email carries the subject, the cover image when one is set, a summary and a link to the published post, not the full post body.
Transactional templates such as OTP codes send right away. Other emails wait until the recipient consents. See [Email sending](#email-sending).

## Quick start (hosted, OAuth)

Hosted server URL:

```
https://mcp.goodsender.com/
```

You sign in to GoodSender in the browser the first time the client connects. To use blog tools, you need a GoodSender workspace with a blog. To send the optional newsletter, set up its sender identity and a public blog address first.

### Claude Desktop

On Free, Pro or Max: open **Customize → Connectors**, choose **Add → Add custom connector**, and enter `https://mcp.goodsender.com/`. Keep the sign-in option so the OAuth flow runs the first time you use the connector.

On Team or Enterprise, an organization owner first adds GoodSender in **Organization settings → Connectors → Add → Custom → Web**. Members can connect it after that.

### Claude Code

```sh
claude mcp add --transport http goodsender https://mcp.goodsender.com/
claude mcp login goodsender
```

Complete the OAuth flow in the browser. Check the connection with `claude mcp get goodsender`, or run `/mcp` in an interactive session.

### Codex

```sh
codex mcp add goodsender --url https://mcp.goodsender.com/
codex mcp login goodsender
```

The Codex CLI and IDE extension share this configuration. The login command completes the browser flow.

### ChatGPT

Turn on developer mode under **Settings → Apps & Connectors → Advanced settings**. Create an app with the server URL `https://mcp.goodsender.com/` and OAuth authentication, then sign in to GoodSender when prompted. Pick the app from the **+** menu in a new chat.

Publishing needs MCP apps with write actions. OpenAI offers these as a beta on Business, Enterprise and Edu workspaces, and an admin may have to allow developer mode. Other plans may connect read-only. Menu names change between ChatGPT releases.

Full guide: [goodsender.com/docs/mcp](https://goodsender.com/docs/mcp/).

## Local install

The local server uses an API key. Create one on the **API keys** page of your GoodSender dashboard. Treat the key as a secret: never commit or share it.

<details>
  <summary><b>MCP Bundle (`.mcpb` file, easiest)</b></summary>

  - Grab the `goodsender.mcpb` file from the [latest release](https://github.com/good-sender/mcp/releases/latest).
  - Double-click the `goodsender.mcpb` file to open it in your AI client.<br/>

    > *Note:*
    > Not every AI client supports MCP bundles or local MCP servers yet.
    > Use a different installation method if nothing happens on double-click.

</details>

<details>
  <summary><b>Docker image / self-hosting</b></summary>

  Run via
  ```sh
  docker run -d -e GOODSENDER_API_KEY=<Your API Key> -v goodsender-mcp-data:/data ghcr.io/good-sender/mcp:latest
  ```

  If your goal is to run the agent using this MCP fully autonomously, set `GOODSENDER_DISABLE_ACTION_GUARDS=true` to skip all action confirmations completely. See [Action confirmation](#action-confirmation).

  or add to `docker-compose.yaml` on your home server
  ```yaml
  services:
    goodsender-mcp:
      image: ghcr.io/good-sender/mcp:latest
      ports:
        - "9889:9889"
      environment:
        GOODSENDER_API_KEY: <Your API Key>
        # GOODSENDER_DISABLE_ACTION_GUARDS: "true"  # skip all action confirmations
      volumes:
        - goodsender-mcp-data:/data
      restart: unless-stopped

  volumes:
    goodsender-mcp-data:
  ```
  and run via
  ```bash
  docker compose up -d
  ```

</details>

<details>
  <summary><b>Manual configuration (JSON)</b></summary>

  - Grab the `binaries.zip` file from the [latest release](https://github.com/good-sender/mcp/releases/latest) (includes MCP `goodsender-mcp-*` and CLI `goodsender-*` binaries).
  - Unzip it somewhere you can easily reference.
  - Modify your AI client config file, adding the MCP server configuration (example for Claude Desktop and Cursor on macOS):
    ```json
    {
      ...
      "mcpServers": {
        "GoodSender": {
          "command": "<path to the unzipped binaries>/goodsender-mcp-darwin-arm64",
          "env": {
            "GOODSENDER_API_KEY": "<Your API key>"
          }
        }
      }
      ...
    }
    ```
    > _For other platforms you must reference a corresponding binary instead of `darwin` (macOS)_

    If your goal is to run the agent using this MCP fully autonomously, set `GOODSENDER_DISABLE_ACTION_GUARDS=true` to skip all action confirmations completely. See [Action confirmation](#action-confirmation).

</details>

### Environment variables

| Variable | Required | Meaning |
|---|---|---|
| `GOODSENDER_API_KEY` | Yes | Your GoodSender API key. |
| `GOODSENDER_DISABLE_ACTION_GUARDS` | No | `true` makes mutating tools run without a confirmation step. See [Action confirmation](#action-confirmation). |
| `GOODSENDER_TELEMETRY` | No | `false` opts out of usage and reliability telemetry. See [Telemetry & privacy](#telemetry--privacy). |

### Action confirmation

Every tool declares whether it only reads, or changes something. Tools that publish, send, delete or change live state are marked destructive, so clients such as Claude ask you before running them.

- **Hosted server** (`mcp.goodsender.com`): that client prompt is the approval step. Tools run when you approve the call, and `confirm_action` is not offered.
- **Local server:** action guards add a second step by default. A tool that publishes, sends, deletes or changes the live blog design returns a confirmation token instead of acting, and `confirm_action` runs it once you approve. Set `GOODSENDER_DISABLE_ACTION_GUARDS=true` in the server environment to skip that step, for example for unattended loops (scheduled agents, CI).

## Email sending

GoodSender sends email as well as blog posts. Permission protects deliverability, so cold outreach is not supported. Email tools work with the hosted server and with a local server.

- 🤝 **Consent handling.** Recipients you add get a consent request by email. Custom emails to a recipient without consent wait in a queue. Emails to recipients who already consented go out right away.
- 🔁 **Consent flow.** You do not track consent yourself. After a recipient consents, their queued emails go out when you ask to send pending emails (`send_pending_emails`) or use another tool that sends email. Nothing is sent while the server is idle.
- ✅ **Transactional templates.** Built-in templates send right away, without a consent step: OTP code, MFA enrollment, new device login, password changed, email changed, order receipt and order completed.
- ✉️ **Formats.** Send plain text, HTML or Markdown to one or more addresses, or to whole groups.
- 📝 **Custom templates.** Create and edit templates with dynamic variables. Preview them in the chat with sample data, send a test email, then save and send by template name.
- 👥 **Recipient groups.** Organize recipients into groups and address a whole group by name.
- 🏷️ **Sender identities.** Manage `From:` identities on a verified domain and refer to them by name.
- 📊 **Health metrics.** Check email health metrics for each sender domain.
- 🛡️ **Where data lives.** Pending emails, custom templates, recipient groups and sender identities are stored in the MCP server's database: on your machine for a local server, on the server host for the hosted connection. Sending uses the GoodSender API. Blog posts, settings and designs are stored on GoodSender servers.

<details>
  <summary><b>Example email prompts</b></summary>

  #### Add 'John Doe &lt;john.doe@example.com&gt;' and 'Jane Doe &lt;jane.doe@example.com&gt;' to the AI newsletter subscribers group
  > ℹ️ This will:
  > - Create/update the recipients in the database
  > - Add them to the "AI newsletter subscribers" recipient group, creating it if needed

  #### Create a GoodSender template for a weekly AI news digest sent to the AI newsletter subscribers group
  > ℹ️ This will:
  > - Create a draft email template in GoodSender format following best practices for email template creation
  > - Display interactive preview of this template draft (if AI client supports it)

  #### Increase the number of news in the digest to 5
  > ℹ️ Done during the template draft creation/editing, this will:
  > - Modify the template accordingly
  > - Display interactive preview of this template draft (if AI client supports it)

  #### Send a test email to me: 'Good Sender &lt;good.sender@example.com&gt;'
  > ℹ️ Done during the template draft creation/editing, this will:
  > - Send an email with mocked data generated from the current template draft only to you

  #### Save the template as "Weekly AI news"
  > ℹ️ Done during the template draft creation/editing, this will:
  > - Convert the current template draft to a persistent template stored in the MCP server's database
  > - Allow sending emails just by mentioning the template name

  #### Gather this week's AI news and send them using the "Weekly AI news" template
  > ℹ️ This will:
  > - Create and enqueue a personalized template-based email for each recipient in the AI newsletter subscribers group
  > - For all recipients who haven't received an email with consent request, will request their consent for receiving emails from you
  > - Send emails to all recipients who granted their email consent
  > - Keep the other emails queued; they go out after the recipient consents, when you send pending emails

</details>

<img width="392" height="539" alt="Example 1" src="https://github.com/user-attachments/assets/155f6fae-61f0-4e56-b503-174793f109e5" />
<img width="392" height="539" alt="Example 2" src="https://github.com/user-attachments/assets/8916165a-68cc-4442-a49a-3f08e93da7ab" />

## Tools

### Blog and newsletter

| Tool | What it does |
|---|---|
| **Posts and newsletter** | |
| `list_posts` | List all posts, drafts and published, with the blog's byline and taxonomy. |
| `get_post` | Get one post, including its markdown body. |
| `create_post` | Create a draft post. It never publishes or sends. |
| `edit_post` | Change a draft or published post. |
| `delete_post` | Permanently delete a post. |
| `create_post_preview` | Create a signed preview URL for a draft or published post. |
| `upload_post_image` | Upload an image (JPEG, PNG, GIF or WebP) for a post and get back its URL. |
| `get_post_distribution` | Show where a post goes when published: the newsletter and the dev.to, X, LinkedIn, Bluesky and Mastodon destinations. |
| `set_post_distribution` | Choose those destinations and review their text, newsletter subject and summary. |
| `publish_post` | Publish the post to the public blog, then act on its distribution plan. |
| `send_post_test` | Send a test email of the post to one inbox. |
| `broadcast_post` | Email a published post's newsletter to consented subscribers, at most once per post. |
| `reannounce_post` | Post a published post to one announce destination (X, LinkedIn, Bluesky or Mastodon) again. |
| **Blog settings and custom domain** | |
| `get_blog` | Get blog settings (title, description, sender, theme, custom domain) and whether a custom design is live. |
| `update_blog` | Create or change blog settings, including SEO title and description. |
| `connect_blog_domain` | Claim a custom hostname for the blog and get the DNS records to add. |
| `get_blog_custom_domain` | Check custom domain status and DNS targets. |
| `remove_blog_custom_domain` | Remove the blog's custom domain. |
| **Blog design** | |
| `blog_design_template_format` | Documentation for the blog design template format. |
| `blog_design_list` | List saved designs, flagging the active one and the stock one. |
| `blog_design_create` | Create a new design from templates and images. |
| `blog_design_edit` | Edit a design's templates. |
| `blog_design_get_latest_checkpoint` | Get the latest version of a design. |
| `blog_design_checkpoint_list` | List the versions of a design. |
| `blog_design_checkpoint_restore` | Go back to an earlier version, deleting the newer ones. |
| `blog_design_save` | Keep a version and delete the older ones. |
| `blog_design_activate` | Make a saved design the live design of the blog. |
| `blog_design_image_upload_url` | Get an upload URL for a logo or favicon. |

### Email

| Tool | What it does |
|---|---|
| **Sending** | |
| `enqueue_email` | Queue an email in plain text, HTML or Markdown to addresses or groups. It is sent once the recipient consents. |
| `enqueue_template_email` | Queue a template-based email. It is sent once the recipient consents. |
| `send_consentless_email` | Send a built-in transactional template (OTP code, MFA enrollment, new device login, password or email changed, order receipt or completion) right away. |
| `send_pending_emails` | Send queued emails whose recipients have consented since they were queued. |
| `send_template_draft_test_email` | Send a test email from a template draft to one recipient. |
| **Templates** | |
| `template_format` | Documentation for the email template format. |
| `create_template_draft` | Start a new template draft. |
| `edit_template` | Edit a template or draft with search-and-replace changes. |
| `get_template` | Get a saved template by name. |
| `get_template_content` | Get a template's current content, including unsaved edits. |
| `render_template_preview` | Render a template preview with sample data. |
| `save_template` | Save a template draft. |
| `list_templates` | List email templates. |
| `delete_template` | Delete a template and the emails created from it. |
| **Recipients and groups** | |
| `create_recipients` | Add recipients and request their consent. |
| `list_recipients` | List recipients with group memberships and their last known consent status. |
| `edit_recipient` | Change a recipient's display name. |
| `delete_recipients` | Permanently delete recipients and their emails. |
| `create_group` | Create a recipient group. |
| `list_groups` | List recipient groups. |
| `add_group_members` | Add recipients to a group. |
| `remove_group_members` | Remove recipients from a group. |
| **Senders** | |
| `create_sender_identity` | Create a `From:` identity on a verified domain. |
| `edit_sender_identity` | Change a sender identity's display name. |
| `list_sender_identities` | List sender identities and whether each domain is verified. |
| `check_sender_domain_stats` | Show email health metrics for each sender domain. Read-only. |
| **Action confirmation (blog and email)** | |
| `confirm_action` | Run an action you approved, for both blog and email tools. Present only on a local server with action guards on (see [Action confirmation](#action-confirmation)). |

## FAQ

**Is there a blog platform with an official MCP server?**
Yes. GoodSender publishes this server for its blog platform. Connect the hosted server at `https://mcp.goodsender.com/` with OAuth, or run it locally. See the [MCP connection guide](https://goodsender.com/docs/mcp/).

**How do I publish a blog post from Claude Code?**
Add the server with `claude mcp add --transport http goodsender https://mcp.goodsender.com/` and sign in with `claude mcp login goodsender`. Then ask Claude Code to draft the post, show the preview and publish it. The [MCP connection guide](https://goodsender.com/docs/mcp/) walks through your first publish.

**Can Codex publish posts to my blog on my own domain?**
Yes. Connect Codex with `codex mcp add goodsender --url https://mcp.goodsender.com/`, then ask it to connect your domain. It returns the DNS records you add at your DNS provider, and published posts appear at that address. Setup steps are in the [MCP connection guide](https://goodsender.com/docs/mcp/).

**Can it send the post as a newsletter at the same time?**
Yes. Select the newsletter in the post's distribution, and publishing emails it to subscribers who have given consent. The blog needs a sending domain, a `From:` address and a public address first. The email has the subject, the cover image when one is set, a summary and a link to the post, not the full body. See [how publishing from Claude and ChatGPT works](https://blog.goodsender.com/blog-from-claude-and-codex-mcp).

**How do I send email from Claude or Claude Code?**
Connect the server as in [Quick start](#quick-start-hosted-oauth), then ask for the email in plain words, for example "Email the March update to the beta-users group." Recipients who already consented get it right away. Anyone else gets a consent request, and the email goes out after they consent, when you send pending emails.

**Which emails skip consent (transactional/OTP)?**
Only the built-in transactional templates: OTP code, MFA enrollment, new device login, password changed, email changed, order receipt and order completed. `send_consentless_email` sends them right away. Custom emails and custom templates always wait for consent.

## How it compares

For side-by-side comparisons with other blog and newsletter platforms, see GoodSender vs [WordPress](https://goodsender.com/compare/wordpress), [Ghost](https://goodsender.com/compare/ghost), [beehiiv](https://goodsender.com/compare/beehiiv) and [Hashnode](https://goodsender.com/compare/hashnode).

## Telemetry & privacy

Telemetry is enabled by default. MCP server sends aggregate usage and reliability metrics to GoodSender to help improve the product.

Typical signals include:
- MCP tool names, call counts, and latency.
- Success and error rates.
- Short error excerpts on failures.
- Background job error codes and frequency.

We do **not** intentionally collect email bodies, recipient addresses, or template contents as part of this telemetry.

You can **opt out** of telemetry collection by setting `GOODSENDER_TELEMETRY=false` in the MCP server environment.

See the **[GoodSender Privacy Policy](https://goodsender.com/privacy)** for how personal data is handled by the service, and the [GoodSender Terms of Service](https://goodsender.com/terms) for the terms of use.

## Links

- [MCP connection guide](https://goodsender.com/docs/mcp/)
- [Blog from Claude and ChatGPT: a walkthrough](https://blog.goodsender.com/blog-from-claude-and-codex-mcp)
- [GoodSender](https://goodsender.com)
- [Privacy policy](https://goodsender.com/privacy)
- [Terms of service](https://goodsender.com/terms)
- Support: [support@goodsender.com](mailto:support@goodsender.com)
- [Telemetry](#telemetry--privacy): on by default, opt out with `GOODSENDER_TELEMETRY=false`
- [Issues](https://github.com/good-sender/mcp/issues)
