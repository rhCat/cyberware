# vendor/wheelhouse — offline static source for the compute environment

Native linux **amd64** (cp312) wheels for `infra/pyenv/requirements.lock`, an offline install accelerator.
The wheel binaries are **gitignored** (≈39 MB, reproducible); `SHA256SUMS` (committed) pins + verifies them.

The compute image (`Dockerfile.compute`) is **multi-arch** (amd64 + arm64): it uses this wheelhouse offline
on amd64, and on other arches falls back to the hash-locked index install (same packages, hash-verified) —
so the wheelhouse need not be rebuilt per arch.

Rebuild: `infra/pyenv/build_wheelhouse.sh` (deterministic, from the hash-pinned lock, linux/amd64).
Verify:  `cd vendor/wheelhouse && shasum -a 256 -c SHA256SUMS`
