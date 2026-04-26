FROM ubuntu:22.04

# Minimal recipe for external CLASS runs used by M110 harness workflows.
# This Dockerfile is documentation-grade and intentionally does not ship
# binaries in the repository.
ARG CLASS_REPO=https://github.com/lesgourg/class_public.git
ARG CLASS_REF=v3.2.0

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
RUN git clone --depth 1 --branch "${CLASS_REF}" "${CLASS_REPO}" class_public \
    && make -C /opt/class_public -j"$(nproc)"

WORKDIR /work
ENTRYPOINT ["/opt/class_public/class"]
