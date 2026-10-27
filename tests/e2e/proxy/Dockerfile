# Traefik routes /hindsight to the control plane built for that base path and
# leaves the path as it is, the way the deployment routes it.
FROM traefik
COPY traefik.yml /etc/traefik/traefik.yml
COPY dynamic.yml /etc/traefik/dynamic.yml
