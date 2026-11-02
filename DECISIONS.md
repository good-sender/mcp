# PR #12 review repair

- Issue #6 acceptance criterion 1 requires square PNG logo and composer assets,
  including dark variants. The package now requires all four references. The
  existing 512 px brand logo is unchanged; the composer PNG is its 64 px Lanczos
  resize. Dark assets preserve the geometry and alpha while swapping the brand
  rust (`#9c3a1a`) and cream (`#fff9f2`) channels, then resizing for the composer.
  Assets were exported with Pillow 13.0.0; the package builder still uses only
  the Python standard library.
- Acceptance criterion 2 requires explicit tool expectations and outcomes for
  all eight cases. Negative cases use `none` for cold-outreach refusal and
  unrelated requests, and `send_consentless_email` for the unverified-sender
  error. Both manifest data and the generated table carry these expectations.
- Visual verification: pending human. This headless run cannot inspect the
  light/dark icons in the plugin directory or composer. That check is skipped;
  automated coverage checks PNG format, dimensions, size and ZIP references.
