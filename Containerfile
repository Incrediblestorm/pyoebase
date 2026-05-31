FROM registry.gitlab.com/sharetec-engineering/devops/containers/oebase:12.2.13
RUN yum install -y python39 python39-pip vim procps-ng net-tools iputils git && yum clean all
RUN mkdir -p -m 775 /var/db/sports
RUN cp /usr/dlc/sports* /var/db/sports || true
RUN for i in `seq 1 10`; do cp --reflink=always -r /var/db/sports /var/db/test$i; done
RUN echo "export PATH=\$PATH:/usr/dlc/bin" >> /etc/profile.d/progress.sh
RUN python