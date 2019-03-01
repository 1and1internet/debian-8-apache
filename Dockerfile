FROM golang as configurability_apache2
MAINTAINER brian.wilkinson@1and1.co.uk
WORKDIR /go/src/github.com/1and1internet/configurability
RUN git clone https://github.com/1and1internet/configurability.git . \
	&& make apache2\
	&& echo "configurability apache2 plugin successfully built"

FROM 1and1internet/debian-8:latest
MAINTAINER brian.wilkinson@1and1.co.uk
ARG DEBIAN_FRONTEND=noninteractive
ARG RPAF_VERSION=tags/v0.8.4
COPY files /
COPY --from=configurability_apache2 /go/src/github.com/1and1internet/configurability/bin/plugins/apache2.so /opt/configurability/goplugins
ENV SSL_KEY=/ssl/ssl.key \
    SSL_CERT=/ssl/ssl.crt \
    DOCUMENT_ROOT=html \
    MAXCONNECTIONSPERCHILD=500
RUN \
  apt-get update && \
  apt-get install -o Dpkg::Options::=--force-confdef -y apache2 cronolog build-essential git apache2-dev && \
  mkdir /tmp/mod_rpaf && \
  git clone https://github.com/gnif/mod_rpaf.git /tmp/mod_rpaf && \
  update-alternatives --install /bin/sh sh /bin/bash 100 && \
  cd /tmp/mod_rpaf && \
  git checkout $RPAF_VERSION && \
  ls -la && \
  make && \
  make install && \
  mkdir -p /var/lock/apache2 && mkdir -p /var/run/apache2 && \
  chmod -R 755 /hooks /init && \
  chmod -R 777 /var/log/apache2 /var/lock/apache2 /var/run/apache2 \
                /etc/apache2/sites-* /etc/apache2/mods-* /etc/apache2/conf-* \
                /var/www && \
  chmod 666 /etc/apache2/ports.conf /etc/DOCUMENT_ROOT && \
  echo "SSLProtocol ALL -SSLv2 -SSLv3" >> /etc/apache2/apache2.conf && \
  echo 'MaxConnectionsPerChild ${MAXCONNECTIONSPERCHILD}' >> /etc/apache2/apache2.conf && \
  sed -i 's/MaxConnectionsPerChild *0/MaxConnectionsPerChild   ${MAXCONNECTIONSPERCHILD}/' /etc/apache2/mods-available/* && \
  sed -i -e 's/Listen 80/Listen 8080/g' /etc/apache2/ports.conf && \
  sed -i -e 's/Listen 443/#Listen 8443/g' /etc/apache2/ports.conf && \
  echo "Listen 8081" >> /etc/apache2/ports.conf && \
  a2enmod deflate rewrite ssl headers macro rpaf cgi expires && \
  a2disconf other-vhosts-access-log && \
  a2enconf vhosts-logging && \
  apt-get -y autoremove build-essential apache2-dev git && \
  rm -rf /tmp/mod_rpaf && \
  rm -rf /var/lib/apt/lists/*

EXPOSE 8080 8443
