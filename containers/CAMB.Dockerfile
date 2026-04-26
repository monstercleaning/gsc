FROM ubuntu:22.04

# Minimal recipe for external CAMB runs used by M110 harness workflows.
# This Dockerfile is documentation-grade and intentionally does not ship
# binaries in the repository.
ARG CAMB_REPO=https://github.com/cmbant/CAMB.git
ARG CAMB_REF=CAMB_1.5.8

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       ca-certificates \
       git \
       make \
       gcc \
       gfortran \
       python3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt
RUN git clone --depth 1 --branch "${CAMB_REF}" "${CAMB_REPO}" CAMB \
    && make -C /opt/CAMB -j"$(nproc)"

WORKDIR /work
ENTRYPOINT ["/opt/CAMB/camb"]
