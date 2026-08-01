# Application Pack and Sidecar Resolver Design

## Pack boundary

`build-runtime.ps1` copies only application/vendor/resource/legal files,
requirements guidance, and dependency metadata. The Python manifest module and
Rust verifier share the same application-only contract: required entry points,
external Python declaration, no weights/caches, and a complete hash inventory.
The build machine may use Python to calculate the manifest; no target-machine
Python or dependency is copied into the artifact.

## Environment selection

The Rust sidecar resolver scans explicit `FIGURESMITH_PYTHON`, project virtual
environments, Windows `py -0p`, PATH commands, and known conda/virtualenv
roots. A supported Python 3.10-3.12 is used only as a base; the resolver creates
`%LOCALAPPDATA%\FigureSmith\python-env` and installs `requirements-bootstrap.txt`
into that isolated environment. The base interpreter is never pip's target.
`FIGURESMITH_MANAGED_PYTHON_DIR` can override the isolated location.

The child always receives the managed interpreter, application `PYTHONPATH`,
loopback settings, strict-offline flags, and the managed environment path.
Inherited source-path hooks are removed. Model requirements are installed only
when the user explicitly copies the command shown by the welcome page.

## Model environment

The dependency contract labels Torch, torchvision, timm, transformers, kornia,
SAM3, and related packages as model scope. The backend reports those packages
without importing them in the main process. GPU probing runs in a disposable
child process because an ABI-incompatible Torch installation can terminate the
interpreter at native load time. Missing model packages do not block the
application after bootstrap readiness.

## UI flow

The splash reports resolver failure and offers one-click isolated-environment
creation/repair followed by an app restart. The welcome page loads status once,
shows the managed environment path and summary cards, and provides a wizard
with environment, SAM3 import, RMBG import, provider, and completion steps.
Model cards show their local path and verification state; import operations show
an indeterminate progress bar until the backend verifies the files. Refresh and
import actions update the same status source; no duplicate polling or stale
model state is retained.
