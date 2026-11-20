# Reference environment: builds the Fortran drivers and serves the web learning tool.
#
#   docker build -t gerald-na .
#   docker run --rm -p 8000:8000 gerald-na          # http://localhost:8000/healthz
#
# Toolchain (pinned so golden and parity results are reproducible):
#   * Ubuntu 24.04 (noble)
#   * gfortran 16 from the ubuntu-toolchain-r/test PPA (package gfortran-16), made the default gfortran
#   * LLVM flang 22 from apt.llvm.org (secondary compiler: `make test-fortran-flang`)
#   * fpm 0.13.0 release binary (sha256-verified)
#   * uv 0.13.8, with a uv-managed CPython 3.15
FROM ubuntu:24.04

ARG GCC_MAJOR=16
ARG LLVM_MAJOR=22
ARG FPM_VERSION=0.13.0
ARG PYTHON_VERSION=3.15

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    UV_PYTHON_INSTALL_DIR=/opt/uv/python \
    UV_LINK_MODE=copy \
    UV_FROZEN=1 \
    UV_NO_PROGRESS=1

# Compilers and build tools.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates curl git gnupg make software-properties-common \
    && add-apt-repository -y ppa:ubuntu-toolchain-r/test \
    && curl -fsSL https://apt.llvm.org/llvm-snapshot.gpg.key \
        | gpg --dearmor -o /usr/share/keyrings/apt.llvm.org.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/apt.llvm.org.gpg] http://apt.llvm.org/noble/ llvm-toolchain-noble-${LLVM_MAJOR} main" \
        > /etc/apt/sources.list.d/llvm.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        "gcc-${GCC_MAJOR}" "gfortran-${GCC_MAJOR}" "flang-${LLVM_MAJOR}" \
    && update-alternatives --install /usr/bin/gfortran gfortran "/usr/bin/gfortran-${GCC_MAJOR}" 100 \
    && update-alternatives --install /usr/bin/gcc gcc "/usr/bin/gcc-${GCC_MAJOR}" 100 \
    && update-alternatives --install /usr/bin/flang flang "/usr/bin/flang-${LLVM_MAJOR}" 100 \
    && gfortran --version | head -n 1 | grep -q " ${GCC_MAJOR}\." \
    && rm -rf /var/lib/apt/lists/*

# fpm (Fortran Package Manager).
RUN curl -fsSL -o /tmp/fpm \
        "https://github.com/fortran-lang/fpm/releases/download/v${FPM_VERSION}/fpm-${FPM_VERSION}-linux-x86_64-gcc-12" \
    && curl -fsSL -o /tmp/fpm.sha256 \
        "https://github.com/fortran-lang/fpm/releases/download/v${FPM_VERSION}/fpm-${FPM_VERSION}-linux-x86_64-gcc-12.sha256" \
    && echo "$(cut -d ' ' -f 1 /tmp/fpm.sha256)  /tmp/fpm" | sha256sum -c - \
    && install -m 0755 /tmp/fpm /usr/local/bin/fpm \
    && rm /tmp/fpm /tmp/fpm.sha256 \
    && fpm --version

# uv and Python.
COPY --from=ghcr.io/astral-sh/uv:0.13.8 /uv /uvx /usr/local/bin/
RUN uv python install "${PYTHON_VERSION}" && chmod -R a+rX /opt/uv

WORKDIR /workspace
RUN chown ubuntu:ubuntu /workspace
USER ubuntu

# Python dependencies first (cached while only sources change).
COPY --chown=ubuntu:ubuntu python/pyproject.toml python/uv.lock python/.python-version python/
RUN uv --directory python sync --frozen --no-install-project

# Repository content served or executed by the app: scans, legacy listings, Fortran sources,
# catalog, study pages, settings and the Python package.
COPY --chown=ubuntu:ubuntu . .
RUN make build-fortran && uv --directory python sync --frozen

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/healthz || exit 1
CMD ["uv", "run", "--project", "python", "gerald-na", "serve", "--host", "0.0.0.0"]
