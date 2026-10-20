# MBBS Question Bank — split build

`docs/` is a generated, deployable version of the single-file master:

```
/Users/johnson/Desktop/MBBS_QBank_AI_Answers.html
```

The master stays untouched. Do **not** edit `docs/index.html` by hand — rebuild it.

## What the split build contains

- `docs/index.html` — ~9.5 MB, no embedded images
- `docs/figures/` — 345 figure files, loaded only when a question shows them
- `docs/.nojekyll` — tells GitHub Pages to serve files directly
- `docs/robots.txt` — asks search engines not to index the site

## Rebuild after editing the master

Double-click **Rebuild Site.command**, or run:

```bash
python3 tools/build_split.py --zip
```

Outputs:

- `docs/index.html`
- `docs/figures/` (content-hashed filenames, so changed figures don't stay cached)
- `MBBS_QBank_split.zip` — for sharing a folder with friends

## Publish with GitHub Desktop + GitHub Pages

1. Open GitHub Desktop → **File → Add Local Repository…**
2. Choose this folder: `MBBS_QBank_Site`
3. If it says it is not a Git repository, click **create a repository** (name: `mbbs-qbank`).
4. Commit the files with the summary `Add split MBBS question bank build`.
5. Click **Publish repository** (top bar).
6. On github.com: repository → **Settings → Pages**.
7. Under **Build and deployment**, choose **Deploy from a branch**.
8. Branch: `main`, folder: `/docs`, then **Save**.
9. Wait 1–3 minutes. The URL appears on the Pages settings page:
   `https://<your-username>.github.io/mbbs-qbank/`

GitHub Desktop does not have a Pages setting; that part is done on github.com.

## Updating the live site

1. Edit the master single file as usual.
2. Double-click **Rebuild Site.command** (or run the Python command).
3. In GitHub Desktop: review changes → commit → **Push origin**.
4. GitHub Pages redeploys automatically in a minute or two.

## Sharing without GitHub

Send `MBBS_QBank_split.zip`. The recipient unzips it and opens `index.html`
in the same folder as `figures/`. For phones, hosting is more reliable than
opening a local file.

## Privacy

- GitHub Pages on free plans is **public**. Anyone with the URL can open it.
- The in-app password is client-side and is not real access control.
- If the bank must stay private, use **Cloudflare Pages + Cloudflare Access**
  (email login, free for small groups) or another private host. The split
  build fits Cloudflare Pages file-size limits.
- `robots.txt` discourages search indexing but does not restrict access.

## File limits

The HTML is ~9.5 MB and the largest figure is ~3.5 MB, both below GitHub's
100 MB per-file limit. Keep the 70 MB master **out of this repository** so
each edit does not add 70 MB to Git history.
