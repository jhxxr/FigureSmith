# Windows application-pack dependencies

FigureSmith no longer attempts to ship CPython, PyTorch, CUDA wheels, or a
fully resolved ML runtime. Those files are too hardware- and driver-specific
for a reliable desktop artifact.

The Windows application pack contains:

- `requirements-runtime.txt`, a reviewable set of user-environment package
  ranges;
- `app/backend/figuresmith/runtime/dependencies.json`, which maps distribution
  names to import names and separates bootstrap, model, generation, and SVG
  scopes;
- `runtime-manifest.json`, a hash inventory of application files only.

At startup the desktop shell scans visible Python 3.10-3.12 candidates and uses
one only as a base. It creates `%LOCALAPPDATA%\FigureSmith\python-env` and
installs bootstrap packages into that isolated environment. The base Python and
other environments are never modified. Torch/torchvision/SAM3 and GPU support
are checked separately by the backend in an isolated child process, so a broken
native Torch installation cannot crash the editor. The welcome page shows the
managed path, missing packages, and a copyable command for the isolated Python.

For local inference, install model packages into the isolated environment after
first launch, choosing the CUDA-compatible Torch pair for the target machine:

```powershell
# Use the exact python.exe path shown by the welcome page.
<isolated-python> -m pip install -r requirements-models.txt
```

Model weights remain external and are imported through the Models page. The
application pack never contains Python executables, wheels, caches, user data,
or model weights.
