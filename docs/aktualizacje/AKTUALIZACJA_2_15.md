# Sebastian 2.15 — Centrum dowodzenia

Nowy ekran główny: kafelki Rekrutacji, panelu Sebastiana, Gwarantów i terminala, z sygnałem działania usług.

```bash
cd ~/SebastianSystem/sebastian-start && source .venv/bin/activate
security add-generic-password -a sebastian -s pl.sebastian.terminal -w   # raz: hasło do terminala
python ~/Downloads/Sebastian_aktualizacja_2_15.py
```

Adresy (tylko Tailscale, zgodnie z ACL): dashboard `:8443`, panel Sebastiana `:10000`, terminal `:9443`.
Panel Rekrutacji zostaje na `:8790`, a Gwaranci na publicznym Funnel. Nazwa sieci i adres IP są w `data/centrum.json`.
