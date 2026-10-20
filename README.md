# MBBS Question Bank — split build

Live site:

**https://johnsonleeky.github.io/mbbs/**

The site is served from the **repository root** (`main` / `/`). GitHub Pages
already deploys from the root, so no `/docs` setting is needed.

`index.html` is generated from the single-file master:

```
/Users/johnson/Desktop/MBBS_QBank_AI_Answers.html
```

The master stays outside this repository. Keep the 70 MB master out of Git so
each edit does not add 70 MB to history.

## Layout

- `index.html` — ~9.5 MB, no embedded images
- `figures/` — 345 figure files, loaded only when a question shows them
- `.nojekyll` — tells GitHub Pages to serve files directly
- `robots.txt` — asks search engines not to index the site
- `tools/build_split.py` — builds the site from the master
- `Rebuild Site.command` — double-click helper for macOS
- `MBBS_QBank_split.zip` — generated shareable zip (ignored by Git)

## Rebuild

Double-click **Rebuild Site.command**, or run from the repository root:

```bash
python3 tools/build_split.py --zip
```

Outputs:

- `index.html`
- `figures/` (content-hashed filenames, so changed figures don't stay cached)
- `MBBS_QBank_split.zip` — only the site files, for sharing

## Publish / update

This repository is already connected to GitHub as `johnsonleeky/mbbs`.

1. In GitHub Desktop, review the changes.
2. Commit with a summary such as `Rebuild split question bank`.
3. Click **Push origin**.
4. GitHub Pages redeploys in 1–3 minutes at the live URL above.

Pages should stay at **Settings → Pages → Deploy from a branch → `main` / `/`**.
If it is ever changed to `/docs`, the root URL will 404.

The old nested URL
`https://johnsonleeky.github.io/mbbs/MBBS_QBank_Site/docs/`
is retired. Both URLs are on the same `johnsonleeky.github.io` origin, so
existing browser progress carries over.

## Sharing without GitHub

Send `MBBS_QBank_split.zip`. The recipient unzips it and opens `index.html`
in the same folder as `figures/`. For phones, hosting is more reliable than
opening a local file.

## Privacy

- GitHub Pages is **public**. Anyone with the URL can open it.
- The in-app password is client-side and is not real access control.
- If the bank must stay private, use **Cloudflare Pages + Cloudflare Access**
  (email login, free for small groups) or another private host. The split
  build fits Cloudflare Pages file-size limits.
- `robots.txt` discourages search indexing but does not restrict access.

## File limits

The HTML is ~9.5 MB and the largest figure is ~3.5 MB, both below GitHub's
100 MB per-file limit.
