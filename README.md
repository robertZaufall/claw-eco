# claw-eco

`claw-eco` is a small static site that compares AI agent frameworks, with a spotlight on the OpenClaw ecosystem and nearby alternatives. The project is a single HTML page designed to be easy to open locally and publish with GitHub Pages.

## Open locally

- Quickest option: open `index.html` directly in your browser.
- Local preview server:

```bash
python3 -m http.server 8000
```

Then visit `http://localhost:8000`.

## Main files

- `index.html` — the full comparison page, including layout, styling, and content.
- `.github/workflows/static.yml` — deploys the repository to GitHub Pages on pushes to `main`.
- `README.md` — this short guide for local preview and repo structure.
