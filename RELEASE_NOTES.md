# v0.8.3 (draft)

> Draft. The version is set by the next `goodsender-mcp-go` release tag; rename this heading if that tag differs. The release workflow regenerates `server.json` from `server.template.json` for that tag, so the new registry description and `remotes` entry go live with it.

GoodSender is a blog platform you run from your AI assistant. This MCP server lets Claude, Claude Code, Codex and ChatGPT draft, preview and publish posts on your blog, on your own domain, and send them to your subscribers as a newsletter.

- **Hosted server with OAuth.** Connect `https://mcp.goodsender.com/` and sign in to GoodSender in the browser. Nothing to install. Setup for each client: [goodsender.com/docs/mcp](https://goodsender.com/docs/mcp/).
- **Local server with an API key.** Use the `.mcpb` bundle or the binaries.

## What changed in this release

- The MCP Registry entry now lists the hosted server (`remotes`: `streamable-http` at `https://mcp.goodsender.com/`) next to the `.mcpb` and Docker packages.
- The registry, README and repository describe GoodSender as a blog and newsletter platform. Email tools are documented under *Email delivery*.
- `blog_design_template_format` documents the template language: set a BCP 47 `lang` attribute on each page template and write all visible template text in the blog's language.

## Changes since v0.2.3

- **Hosted, multi-user mode (v0.3.0).** One server serves many users. OAuth sign-in, including ChatGPT apps, plus a CLI mode via [good-sender/cli](https://github.com/good-sender/cli).
- **Blog and posts (v0.4.0).** Blog settings, custom domain, drafts, previews, publishing and newsletter broadcast.
- **Post images and distribution (v0.5.x).** `upload_post_image` works in local and hosted mode. `get_post_distribution`, `set_post_distribution` and `reannounce_post`: publishing shows the exact plan (newsletter, dev.to, X, LinkedIn, Bluesky, Mastodon) and you confirm it. Post cover images. The CLI keeps one API key per workspace.
- **Blog design (v0.6.0).** Create, edit, preview, save and activate a custom blog design, with logo and favicon uploads. Cover image alt text, author bylines, and SEO title and description overrides for the blog and each post. `GET /health` reports the server version.
- **Design state (v0.7.x).** `get_blog` reports whether a custom design is live. Activating a design and restoring a checkpoint ask for confirmation.
- **v0.8.x.** Hashnode removed from the distribution choices. `create_recipients` registers recipients already known locally.
