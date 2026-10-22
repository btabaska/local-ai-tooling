# docker/strata — Strata engine run config (2026-10-22)

`strata-iq3_s.json` is a reference copy of the LIVE run config at
`/opt/llm/strata/install/strata-iq3_s.json` (inside the strata container:
`/data/install/strata-iq3_s.json`). It lives on the data subvolume, not in git,
so this copy is the rebuild record. It holds no secret (the key is only in the
per-launch file `/data/state/strata/launch/docker.json`, regenerated each start).

Setup wrote it; three keys were added by hand and MUST survive a reinstall:

| key | why |
| --- | --- |
| `"lazy_load": true` | idle with NO VRAM; llama-swap's `strata` shim POSTs /load. Without it the container grabs the card at boot and fights q38. |
| `--resident-experts` (args) | resident low-RAM mode: RAM holds only the experts the GPU cache does not (36.4 GiB pinned vs 46.8 GiB all-in-RAM). Measured 120 vs 127 tok/s decode, RAM available while loaded ~16 GB vs ~6 GB. |
| `--vram-reserve-mib 1200` (args) | default left 457 MiB free -> Strata warns the driver can page VRAM to RAM (decode collapses); Apollo NVENC / desktop growth needs headroom. |

Each container start rebuilds the per-launch file FROM this one (user keys are
kept), so edit this file (container stopped), not docker.json. `POST /config`
on the running server writes docker.json only and is lost on restart.

Restore after a volume wipe: `docker compose up -d strata` (downloads + prepares,
~90 GB), `docker stop strata`, `sudo cp docker/strata/strata-iq3_s.json
/opt/llm/strata/install/`, `docker start strata`. Runbook (Home repo):
`foss-setup/wiki/docs/runbooks/strata.md`.
