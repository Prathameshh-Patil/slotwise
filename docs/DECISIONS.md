# Design decisions

One line per decision, with the reason.

- Python 3.12 in Docker (not the 3.14 on the dev machine): every library in the stack supports it well, and Docker makes the local version irrelevant.
- Monorepo (backend and frontend in one repo): one place for a reviewer to look, one CI workflow, and front-end and back-end changes ship together.
- MIT license: the simplest permissive license, standard for portfolio projects.
- Git over SSH instead of HTTPS: SSH keys aren't limited by OAuth token scopes, so pushing workflow files works without extra permissions.
