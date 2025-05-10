#!/bin/bash
# Skript zum Erstellen einer Conda-Umgebung für das Blutgruppen-Analyse Dashboard

# Conda-Umgebung erstellen mit Python 3.9
conda create -n ba python=3.9 -y

# Aktiviere die Umgebung
conda activate ba

# Installiere benötigte Pakete
conda install -c conda-forge pandas dash dash-bootstrap-components -y

# Bestätigungsnachricht ausgeben
echo "Conda-Umgebung 'ba' wurde erstellt und aktiviert."
echo "Installierte Pakete:"
conda list

echo ""
echo "Um die Umgebung zu aktivieren, verwende: conda activate ba"
echo "Um das Dashboard zu starten: python app.py"