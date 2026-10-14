FROM python:3.13-slim-trixie@sha256:3dd7cc108ec1493442514f5c2a871af6af0ec31d768ff6e378a93340c3b3db5f
LABEL org.opencontainers.image.source="https://github.com/AlexMatter1512/umbrel-store"
COPY docker/install.sh /tmp/install-surf.sh
RUN /bin/sh /tmp/install-surf.sh && rm /tmp/install-surf.sh
COPY surfhome-surf/hooks/runtime/proxy.py surfhome-surf/hooks/runtime/healthcheck.py surfhome-surf/hooks/runtime/chromium.sh surfhome-surf/hooks/runtime/entrypoint.sh surfhome-surf/hooks/runtime/SURF-LICENSE.txt surfhome-surf/hooks/runtime/SURF-THIRD-PARTY-NOTICES.md /opt/surf-umbrel/
RUN install -m 755 /opt/surf-umbrel/chromium.sh /usr/local/bin/chromium
ENV SURF_HOME=/data/surf HOME=/data PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 CHROME_NO_SANDBOX=1 CHROME=/usr/local/bin/chromium SURF_CONTENT_BLOCKER_DOWNLOAD=0
ENTRYPOINT ["/bin/sh", "/opt/surf-umbrel/entrypoint.sh"]
