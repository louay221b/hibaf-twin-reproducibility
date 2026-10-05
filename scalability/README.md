# Platform-independent scalability experiments H, I and J

These experiments are deterministic closed-form / enumerative analyses. They use **no random seed** and are not tied to any named hardware platform.

## Run

```bash
sh run_all.sh
```

## Experiment H — HECM sensitivity

Uses the DT count

```text
C_DT(N) = 2N + 2
```

and sweeps DT load, reporting-window duration and generic HECM execution time. It reports feasibility, utilization and the maximum admissible HECM time.

## Experiment I — idealized DT workers

Uses

```text
C_DT_parallel(N,k) = 2 + 2*ceil(N/k)
```

where the first two HECM are the serial station-container signature verification and the per-report checks are ideally distributed across `k` workers. Scheduling, synchronization, contention and communication overhead are excluded.

## Experiment J — collector parallelism

Uses the complete all-valid pond data path

```text
C_collector(n) = 2n + 2
```

with collectors processed in `ceil(P/k)` waves, followed by the station and DT stages.

For `P=200, n=20, N=4000`, the corrected endpoints are **16803 HECM** sequential and **8445 HECM** with all collectors parallel.

## Methodological boundary

All results here are platform-independent analytical/simulation outputs, not measured Raspberry Pi, ESP32, or other hardware results.
