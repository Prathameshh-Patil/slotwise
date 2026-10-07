# Learning notes

What we built in each phase, why it is designed that way, and what the alternative would have been.

## Phase 0: Machine setup and repository

**What we built.** An empty but organised project: the folder layout for the back end, front end, scripts and docs; an MIT license; a `.gitignore`; an `.env.example`; and a public GitHub repo with `main` pushed to it.

**Why it is designed this way.**
- *Monorepo.* The back end and front end live in one repository, so one pull request can change both sides of a feature and one CI workflow tests everything. The alternative is two repos, which suits big teams that release separately but adds coordination work for no benefit here.
- *`.gitkeep` files.* Git tracks files, not folders, so an empty folder disappears from the repo. An empty placeholder file keeps the structure visible on GitHub. We delete them as real files arrive.
- *`.gitignore` before the first commit.* `.env` holds secrets (database passwords, the JWT signing key). Ignoring it from day one means a secret can never be committed by accident. Removing a secret from git history afterwards is painful, and it should be treated as leaked anyway. `.env.example` is committed instead: it lists the variable names with no real values.
- *SSH for git pushes.* The GitHub CLI login lacked the `workflow` permission that GitHub requires before accepting files under `.github/workflows/`. We switched git to an SSH key: the private key stays on the laptop, the public key is registered on GitHub, and pushes are authenticated by proving we hold the private key. The alternative was to grant the CLI token the extra permission (`gh auth refresh -s workflow`).

**Git commands used.**
- `git init -b main`: turns a folder into a git repository, with the first branch named `main`.
- `git add .`: stages every changed file, which means choosing what goes into the next snapshot.
- `git commit -m "..."`: saves the staged files as a snapshot with a message.
- `git remote set-url origin <url>`: `origin` is the nickname for the GitHub copy of the repo. This changes the address git uses to reach it.
- `git push -u origin main`: uploads local commits on `main` to GitHub. `-u` remembers the pairing, so later a plain `git push` is enough.
- `gh repo create`: creates the repository on GitHub from the terminal.

**How to check it.** Open https://github.com/Prathameshh-Patil/slotwise, then run `git status` in `~/slotwise` and expect "nothing to commit, working tree clean".
