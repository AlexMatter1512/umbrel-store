# Optional prebuilt image for quicker installs. The store also works with the
# public Python image, provisioning dependencies using the same bootstrap.
FROM python:3.13-slim-trixie@sha256:3dd7cc108ec1493442514f5c2a871af6af0ec31d768ff6e378a93340c3b3db5f
COPY surfhome-surf/hooks/runtime/bootstrap.sh /opt/surf-umbrel/bootstrap.sh
RUN /bin/sh /opt/surf-umbrel/bootstrap.sh --install-only
COPY surfhome-surf/hooks/runtime /opt/surf-umbrel
ENV SURF_HOME=/data/surf HOME=/data PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 CHROME_NO_SANDBOX=1
ENTRYPOINT ["/bin/sh", "/opt/surf-umbrel/bootstrap.sh"]
