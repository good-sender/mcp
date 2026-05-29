<img width="1280" height="460" alt="GoodSender MCP banner" src="https://github.com/user-attachments/assets/0e4636a3-659c-4e28-ae2f-e52cdb5d4019" />

## Features

- 🛡️ Local server
  - Email contents, custom templates, recipient groups and sender identities are stored only on your machine.
- ✉️ Send emails in **plain text**, **HTML** or **Markdown** to one or more recipients.
- ✅ Send **consentless** transactional emails using built-in templates (OTP, MFA, Order Completion, etc.)
- 🤝 Automatic consent flow handling.
  - Recipients added via MCP receive the consent email.
  - Emails are queued locally until recipient grants the consent to receive them.
- 📝 Create, edit and store custom templates with dynamic variables.
  - Interactive template previews for quick design iteration.
  - Send test email to verify template rendering.
- 👥 Organize recipients into groups and reference them all by group name.
- 🏷️ Manage sender identities (`From:` header) and reference them by name.
- 📊 Monitor email health metrics.

## Installation

<details>
<summary>

### MCP Bundle (`.mcpb` file, easiest)

</summary>

- Grab the `goodsender.mcpb` file from the [latest release](https://github.com/good-sender/mcp/releases/latest).
- Double-click the `goodsender.mcpb` file to open it in your AI client.
  > *Note:*
  >
  > Not every AI client supports MCP bundles or local MCP servers yet.
  > Use a different installation method if nothing happens on double-click.

</details>

<details>
<summary>

### Docker image / self-hosting

</summary>

Run via
```sh
docker run -d -e GOODSENDER_API_KEY=<Your API Key> ghcr.io/good-sender/mcp:latest
```

or add to `docker-compose.yaml` on your home server
```yaml
services:
  goodsender-mcp:
    image: ghcr.io/good-sender/mcp:latest
    ports:
      - "9889:9889"
    environment:
      GOODSENDER_API_KEY: <Your API Key>
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
<summary>

### Manual configuration (JSON)

</summary>

- Grab the `binaries.zip` file from the [latest release](https://github.com/good-sender/mcp/releases/latest).
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

</details>

## Usage examples

<img width="441" height="607" alt="Example 2" src="https://github.com/user-attachments/assets/155f6fae-61f0-4e56-b503-174793f109e5" />
<img width="441" height="607" alt="Example 3" src="https://github.com/user-attachments/assets/8916165a-68cc-4442-a49a-3f08e93da7ab" />

<details>
<summary><code>Add `John Doe &lt;john.doe@example.com&gt;` and `Jane Doe &lt;jane.doe@example.com&gt;` to the AI newsletter subscribers group</code></summary>

> ℹ️ This will:
> - Create/update the recipients in the database
> - Add them to the "AI newsletter subscribers" recipient group, creating it if needed

</details>

<details>
<summary><code>Create a GoodSender template for a weekly AI news digest sent to the AI newsletter subscribers group</code></summary>

> ℹ️ This will:
> - Create a draft email template in GoodSender format following best practices for email template creation
> - Display interactive preview of this template draft (if AI client supports it)

</details>

<details>
<summary><code>Increase the number of news in the digest to 5</code></summary>

> ℹ️ Done during the template draft creation/editing, this will:
> - Modify the template accordingly
> - Display interactive preview of this template draft (if AI client supports it)

</details>

<details>
<summary><code>Send a test email to me: `Good Sender &lt;good.sender@example.com&gt;`</code></summary>

> ℹ️ Done during the template draft creation/editing, this will:
> - Send an email with mocked data generated from the current template draft only to you

</details>

<details>
<summary><code>Save the template as "Weekly AI news"</code></summary>

> ℹ️ Done during the template draft creation/editing, this will:
> - Convert the current template draft to a persistent template stored in the local database
> - Allow sending emails just by mentioning the template name

</details>

<details>
<summary><code>Gather this week's AI news and send them using the "Weekly AI news" template</code></summary>

> ℹ️ This will:
> - Create and enqueue a a personalized template-based email for each recipient in the AI newsletter subscribers group
> - For all recipients who haven't received an email with consent request, will request their consent for receiving emails from you
> - Send emails to all recipients who granted their email consent
> - Monitor all recipients with pending consent and send the email as soon as they grant it

</details>

## Telemetry & privacy

Telemetry is enabled by default. MCP server sends aggregate usage and reliability metrics to GoodSender to help improve the product.

Typical signals include:
- MCP tool names, call counts, and latency.
- Success and error rates.
- Short error excerpts on failures.
- Background job error codes and frequency.

We do **not** intentionally collect email bodies, recipient addresses, or template contents as part of this telemetry.

You can **opt out** of telemetry collection by setting `GOODSENDER_TELEMETRY=false` in the MCP server environment.

See the **[GoodSender Privacy Policy](https://joylabs.com/legal/privacy-policy)** for how personal data is handled by the service.
