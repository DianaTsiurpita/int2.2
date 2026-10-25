# ---- 1. Base image: small Linux with Python 3.12 -----------------------
FROM python:3.12-slim-bookworm

# ---- 2. Add the uv binary ----------------------------------------------
# Copied from the official uv image — no apt-get or pip needed.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Pre-compile .pyc files (faster start-up) and copy instead of hardlink.
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# ---- 3. Dependencies (cached layer) -------------------------------------
WORKDIR /app

# Copy ONLY the dependency manifests first. Docker caches each step:
# this one re-runs only when these two files change — not on every
# code edit.
COPY pyproject.toml uv.lock ./

# Create /app/.venv and install exactly the versions pinned in uv.lock.
# --frozen = never re-resolve, just use the lockfile as-is.
RUN uv sync --frozen --no-dev

# ---- 4. Application code (changes often → its own layer) ----------------
COPY app ./app

# Make /app/.venv/bin (uvicorn, python, ...) visible on the PATH.
ENV PATH="/app/.venv/bin:$PATH"

# Documentation only: tells the reader which port the app listens on.
EXPOSE 8000

# ---- 5. What runs when the container starts ------------------------------
# 0.0.0.0 = listen on ALL interfaces. Binding to 127.0.0.1 instead would
# make the server unreachable through -p port forwarding.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]