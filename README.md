<img width="1280" height="460" alt="GoodSender MCP banner" src="https://github.com/user-attachments/assets/8f26f913-eb4b-4c3a-b495-0cd2e3ea98ec" />

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

### MCP Bundle (`.mcpb` file)

- Grab the `goodsender.mcpb` file from the [latest release](https://github.com/good-sender/mcp/releases/latest).
- Double-click the `goodsender.mcpb` file to open it in your AI client.
  > _Not every AI client supports local MCP servers or MCP bundles yet._
  > _Use a different installation method if nothing happens on double-click._

### Docker image / self-hosting

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

### Manual configuration

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
