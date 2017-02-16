FROM nathanhoad/gbulb-base

ARG PYTHON_VERSION
ARG GOBJECT_CHECKSUM=779effa93f4b59cdb72f4ab0128fb3fd82900bf686193b570fd3a8ce63392d54
ARG GOBJECT_BASE_VERSION=3.14
ARG GOBJECT_VERSION=3.14.0

ENV HOME=/root/
ENV PYENV_ROOT=$HOME/.pyenv
ENV PATH=$PYENV_ROOT/shims:$PYENV_ROOT/bin:$PATH

RUN pyenv install $PYTHON_VERSION
RUN pyenv global $PYTHON_VERSION

RUN curl -L "https://ftp.gnome.org/pub/GNOME/sources/pygobject/$GOBJECT_BASE_VERSION/pygobject-$GOBJECT_VERSION.tar.xz" -o pygobject.tar.xz
RUN echo "$GOBJECT_CHECKSUM pygobject.tar.xz" > pygobject.checksum
RUN sha256sum --check pygobject.checksum
RUN tar xvf pygobject.tar.xz

WORKDIR pygobject-$GOBJECT_VERSION

# pygobject enforces c90 in configure, in a "you're not getting past this" kind
# of way. From CPython 3.6.0, they (quite reasonably) moved to c99, and
# introduced some c++ style comments to really rub it in, which doesn't go well
# with gobject's c90. So this gross sed is to get us those wonderous comments.
RUN sed -i 's/-std=c90/-std=c99/g' configure
RUN ./configure --prefix="$PYENV_ROOT/versions/$PYTHON_VERSION" --enable-cairo=no
RUN make install
RUN pip install pytest
