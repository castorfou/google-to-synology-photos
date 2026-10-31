FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm

# Supprimer la source Yarn cassée héritée de l'image de base
RUN rm -f /etc/apt/sources.list.d/yarn.list \
    /usr/share/keyrings/yarnkey.gpg \
    /etc/apt/sources.list.d/yarn.list.save 2>/dev/null || true

# ExifTool : écrit les dates et positions manquantes dans les photos envoyées
RUN apt-get update -qq && apt-get install -y -qq libimage-exiftool-perl

# Créer le répertoire cache avec les bons droits avant le montage du volume uv
# Sans ça, Docker crée /home/vscode/.cache en root lors du mount, ce qui bloque pre-commit
RUN mkdir -p /home/vscode/.cache && chown vscode:vscode /home/vscode/.cache
