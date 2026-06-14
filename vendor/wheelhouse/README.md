# vendor/wheelhouse — offline static source for the compute environment

Native linux (cp312) wheels for `infra/pyenv/requirements.lock`, the local/air-gapped install source.
The wheel binaries are **gitignored** (≈39 MB, reproducible); `SHA256SUMS` (committed) pins + verifies them.

Rebuild: `infra/pyenv/build_wheelhouse.sh` (deterministic, from the hash-pinned lock, linux/amd64).
Verify:  `cd vendor/wheelhouse && shasum -a 256 -c SHA256SUMS`
