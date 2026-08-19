# Odoo 19 build image — bakes custom addons + python deps into the official image
FROM odoo:19.0

USER root

# Custom addons live in ./addons at repo root (one folder per module)
COPY ./addons /mnt/extra-addons

# Optional extra python deps used by custom addons
COPY ./requirements.txt /tmp/requirements.txt
RUN if [ -s /tmp/requirements.txt ]; then \
        pip3 install --no-cache-dir --break-system-packages -r /tmp/requirements.txt ; \
    fi

USER odoo
