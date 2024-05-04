FROM ubuntu:24.04

# Disable pip's warnings and SDL audio
ENV PIP_ROOT_USER_ACTION=ignore \
    PIP_NO_WARN_SCRIPT_LOCATION=0 \
    SDL_AUDIODRIVER=dummy

# Run apt non-interactively; use ARG so this only applies while building the image
ARG DEBIAN_FRONTEND="noninteractive"

# Add deadsnakes
RUN apt-get update -y && \
    apt-get install --no-install-recommends -y software-properties-common && \
    add-apt-repository ppa:deadsnakes/ppa

# Install System python
RUN apt-get update -y && \
    apt-get install --no-install-recommends -y \
        libgirepository1.0-dev \
        gir1.2-gtk-3.0 \
        libcairo2-dev \
        build-essential \
        git \
        python3.8-dev \
        python3.8-venv \
        python3.9-dev \
        python3.9-venv \
        python3.10-dev \
        python3.10-venv \
        python3.11-dev \
        python3.11-venv \
        python3-dev \
        python3-venv \
        python3.13-dev \
        python3.13-venv \
        python3-pip

RUN groupadd beeware && \
    useradd brutus -g beeware --home /home/brutus && \
    mkdir -p /home/brutus && chown brutus:beeware /home/brutus

# Use the brutus user for operations in the container
USER brutus

# Set the working directory
WORKDIR /home/brutus/gbulb

CMD /bin/bash
