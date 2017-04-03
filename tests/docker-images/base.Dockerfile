FROM centos:7
RUN yum install -y openssl-devel zlib-devel gtk3-devel gobject-introspection-devel libffi-devel bzip2-devel which gcc make git libtool bzip2
RUN git clone https://github.com/yyuu/pyenv ~/.pyenv
