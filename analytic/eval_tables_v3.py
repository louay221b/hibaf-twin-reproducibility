#!/usr/bin/env python3
"""LaTeX tables for the restructured evaluation (all values computed here from result files)."""
import json, math, importlib.util
import pandas as pd
spec = importlib.util.spec_from_file_location("ea2", "/home/claude/sim/eval_analytic2.py")
import sys
ea2 = importlib.util.module_from_spec(spec); spec.loader.exec_module(ea2)
c_msm, C1 = ea2.c_msm, ea2.C1
T = "/home/claude/paper_v3/tables"
import os; os.makedirs(T, exist_ok=True)
out = {}

# ---------- operation counts per reporting window (all valid), example deployment
S, r, P, theta = 100, 3, 4, 0.25           # 100 sensors, one report per 10 s (3 per 30 s window), 4 ponds
N = S * r; npond = N // P
rows = [
 ("Sensor (each)", r"$r$ HECM; 2 MSM(2)", r"$r$", r"$r{+}1$ (+1/epoch)", r"$r$ Enc.", r + 2*C1, r + 4),
 ("Collector (each)", r"1 HECM; 2 MSM(2); 1 MSM($2n_p{+}1$)", r"$n_p$", "--", "--", 1 + 2*C1 + c_msm(npond), 1 + 4 + (2*npond + 1)),
 ("Station", r"2 HECM; 1 MSM($2P{+}1$)", "--", "--", "--", 2 + c_msm(P), 2 + (2*P + 1)),
 ("Back end", r"1 MSM(2); 1 MSM($2\theta N{+}1$)", r"$\theta N$", r"$N{+}S/E$", r"$N$ Dec.", C1 + c_msm(round(theta*N)), 2 + (2*round(theta*N) + 1)),
]
body = "\n".join(f"{a} & {b} & {c} & {d} & {e} & {f:.1f} & {g:.0f}\\\\" for a, b, c, d, e, f, g in rows)
open(f"{T}/tab_opcount.tex", "w").write(r"""\begin{table*}[!t]
\caption{Cryptographic Operations per Reporting Window (All-Valid Normal Path). MSM($m$): One $m$-Term Multi-Scalar Multiplication. The Last Two Columns Give HECM Equivalents for $S{=}100$ Sensors, One Report per 10~s ($r{=}3$, $N{=}300$), $P{=}4$ Collectors ($n_p{=}75$) and $\theta{=}0.25$, With the Measured MSM Cost Ratios (HiBaF-MSM) and With Independent Scalar Multiplications (Base)}
\label{tab:opcount}
\centering\footnotesize\setlength{\tabcolsep}{4pt}
\begin{tabular}{@{}llllrrr@{}}
\toprule
Tier & Group operations & $H_2$ & PRF & AEAD & HiBaF-MSM & Base\\
\midrule
""" + body + r"""
\bottomrule
\end{tabular}

\vspace{1mm}\raggedright\footnotesize
Base counts each $m$-term check as $m$ scalar multiplications (group additions, 0.4\% of an HECM each, omitted). Link MACs (one per report at sensor and collector) and the TTP's revocation-list signature (one per update, not per window) are omitted.
\end{table*}
""")
out["opcount"] = {a: dict(msm=f, base=g) for a, b, c, d, e, f, g in rows}

# ---------- single-report comparison with signcryption schemes (draft Table IV rows, reference timings)
T_HECM_REF = 2.20                            # ms, reported in [11]; used only as an external reference for comparability
rho_large = 0.33                             # measured MSM cost per signature for n >= 50 (Table l1: 0.32-0.34)
ref_rows = [
 (r"\cite{TajiGhanimi2024HomomorphicHECSigncryption}", r"$4T_{\rm HECM}\approx8.80$", r"$3T_{\rm HECM}\approx6.60$", r"$7T_{\rm HECM}\approx15.40$", "580"),
 (r"\cite{Mandal2020CertificatelessSigncryption}", r"$8T_{\rm ECPM}\approx33.92$", r"$6T_{\rm ECPM}\approx25.44$", r"$14T_{\rm ECPM}\approx59.36$", "900"),
 (r"\cite{Qiu2019MultiMessageMultiReceiver}", r"$4T_{\rm ECPM}\approx16.96$", r"$4T_{\rm ECPM}\approx16.96$", r"$8T_{\rm ECPM}\approx33.92$", "870"),
 (r"\cite{Karati2019GeneralizedSigncryption}", r"$3T_{\rm BP}{+}5T_{\rm PM}\approx273.05$", r"$T_{\rm BP}{+}4T_{\rm PM}\approx162.30$", r"$4T_{\rm BP}{+}9T_{\rm PM}\approx435.35$", "5220"),
 (r"\cite{Su2020EcologicalCLMS}", r"$4T_{\rm ECPM}\approx16.96$", r"$3T_{\rm ECPM}\approx12.72$", r"$7T_{\rm ECPM}\approx29.68$", "580"),
 (r"\cite{Ali2020HybridSigncryptionVANET}", r"$2T_{\rm BP}{+}3T_{\rm PM}\approx171.85$", r"$2T_{\rm BP}{+}2T_{\rm PM}\approx141.30$", r"$4T_{\rm BP}{+}5T_{\rm PM}\approx313.15$", "3172"),
 (r"\cite{Gopisetti2024CLAggSigncryptionIIoT}", r"$4T_{\rm ECPM}\approx16.96$", r"$2T_{\rm ECPM}\approx8.48$", r"$6T_{\rm ECPM}\approx25.44$", "740"),
 (r"\cite{Zhou2023HeterogeneousSigncryptionIoT}", r"$3T_{\rm ECPM}\approx12.72$", r"$4T_{\rm ECPM}\approx16.96$", r"$7T_{\rm ECPM}\approx29.68$", "900"),
]
rcv1 = 2 * C1; tot1 = 1 + rcv1; rcvb = 2 * rho_large; totb = 1 + rcvb
hib = [
 (r"HiBaF-Twin, single report", rf"$1T_{{\rm HECM}}\approx{T_HECM_REF:.2f}$", rf"${rcv1:.2f}T_{{\rm HECM}}\approx{rcv1*T_HECM_REF:.2f}$", rf"${tot1:.2f}T_{{\rm HECM}}\approx{tot1*T_HECM_REF:.2f}$", "1224"),
 (r"HiBaF-Twin, batch $n{\ge}50$", rf"$1T_{{\rm HECM}}\approx{T_HECM_REF:.2f}$", rf"${rcvb:.2f}T_{{\rm HECM}}\approx{rcvb*T_HECM_REF:.2f}$", rf"${totb:.2f}T_{{\rm HECM}}\approx{totb*T_HECM_REF:.2f}$", "1224"),
]
body = "\n".join(" & ".join(x) + r"\\" for x in ref_rows) + "\n\\midrule\n" + "\n".join(r"\textbf{" + x[0] + "} & " + " & ".join(x[1:]) + r"\\" for x in hib)
open(f"{T}/tab_schemes.tex", "w").write(r"""\begin{table*}[!t]
\caption{Single-Report Dominant Computation (ms) and Communication Cost. Timings Are Reference Calculations Within the Primitive Family of Each Scheme ($T_{\rm HECM}=2.20$~ms From~\cite{TajiGhanimi2024HomomorphicHECSigncryption}); HiBaF-Twin With $\theta=1$ (Collector and Back End Both Verify)}
\label{tab:schemes}
\centering\footnotesize
\begin{tabular}{@{}lcccc@{}}
\toprule
Scheme & Sender & Receiver(s) & Total & Comm.\ (bits)\\
\midrule
""" + body + r"""
\bottomrule
\end{tabular}

\vspace{1mm}\raggedright\footnotesize
HiBaF-Twin receiver cost: one 2-term MSM ($1.15\,T_{\rm HECM}$) at the collector and one at the back end; in batches of $n\ge50$ about $0.33\,T_{\rm HECM}$ per signature at each tier (Table~\ref{tab:l1}). Communication: the 153-byte report with an 8-byte reading, including the 64-byte commitment $U_i$, 32-byte response and 8-byte link tag. The schemes provide different services (several are signcryption with aggregation); the table compares dominant cost only.
\end{table*}
""")
out["schemes"] = dict(rcv1=rcv1, tot1=tot1, rcvb=rcvb, totb=totb, ms=[rcv1*T_HECM_REF, tot1*T_HECM_REF, rcvb*T_HECM_REF, totb*T_HECM_REF])

# ---------- ablations B2 (semi-flat) and B3 (no beacon processing), full audit theta=1, n=20 per collector
b2 = []
for Nsite in [500, 1000, 2000, 4000]:
    P2 = Nsite // 20
    hib_base = (2*20 + 2) + (2*P2 + 1) + (2*Nsite + 2)
    b2_base = (2*Nsite + 1) + (2*Nsite + 2)
    hib_msm = (c_msm(20) + 1) + (c_msm(P2) + 1) + (C1 + c_msm(Nsite))
    b2_msm = (c_msm(Nsite) + 1) + (C1 + c_msm(Nsite))
    b2.append(dict(N=Nsite, base_hib=hib_base, base_b2=b2_base, base_gain=100*(b2_base-hib_base)/hib_base,
                   msm_hib=hib_msm, msm_b2=b2_msm, msm_gain=100*(b2_msm-hib_msm)/hib_msm))
out["B2"] = b2
S3, P3 = 100, 4
out["B3"] = dict(S=S3, P=P3, base_saved=2*S3 + 2*P3 + 1, msm_saved=(S3 + P3)*C1 + 1)
json.dump(out, open("/home/claude/sim/analytic/tables_v3.json", "w"), indent=1, default=float)
print(json.dumps(out, indent=1, default=float))

# ---------- energy table (from analytic/energy.csv)
E = pd.read_csv("/home/claude/sim/analytic/energy.csv").set_index("cost")
cols = [("earlier", "earlier values"), ("emu_low", "emulated, low"), ("emu_high", "emulated, high")]
def fmt(x, d=2): return f"{x:.{d}f}"
lines = []
lines.append("$T_{\\rm HECM}$ ESP32 / Pi~4 (ms) & " + " & ".join(f"{fmt(E.loc[k,'T_esp_ms'],1)} / {fmt(E.loc[k,'T_pi_ms'],2)}" for k, _ in cols) + r"\\")
lines.append(r"\midrule \multicolumn{4}{@{}l}{\textit{Sensor (ESP32, $P_{\rm active}=0.264$~W)}}\\")
lines.append("Report construction (mJ) & " + " & ".join(fmt(E.loc[k,'E_report_mJ']) for k, _ in cols) + r"\\")
lines.append("Beacon + RL verification, per window (mJ) & " + " & ".join(fmt(E.loc[k,'E_window_sensor_mJ']) for k, _ in cols) + r"\\")
lines.append(r"\midrule \multicolumn{4}{@{}l}{\textit{Collector (Raspberry Pi 4, $P_{\rm active}=3.4$~W), one batch of $n=100$ reports}}\\")
for lab, key in [("Individual verification (J)", "E_ind_100_J"), ("Base batch test (J)", "E_base_100_J"), ("HiBaF-MSM batch (J)", "E_msm_100_J")]:
    lines.append(lab + " & " + " & ".join(fmt(E.loc[k, key], 3) for k, _ in cols) + r"\\")
lines.append(r"\midrule \multicolumn{4}{@{}l}{\textit{Collector, $n=100$, 50\% replay-related traffic (Monte Carlo means)}}\\")
for lab, key in [("Base, no pre-filter (B4) / filtered (J)", ("E_replay50_base_b4_J", "E_replay50_base_f_J")), ("HiBaF-MSM, B4 / filtered (J)", ("E_replay50_hib_b4_J", "E_replay50_hib_f_J"))]:
    lines.append(lab + " & " + " & ".join(f"{fmt(E.loc[k, key[0]],2)} / {fmt(E.loc[k, key[1]],2)}" for k, _ in cols) + r"\\")
open(f"{T}/tab_energy.tex", "w").write(r"""\begin{table}[!t]
\caption{Computational Energy $E=P_{\rm active}T_{\rm exec}$ for Three Platform Cost Sets}
\label{tab:energy}
\centering\footnotesize\setlength{\tabcolsep}{2.5pt}
\resizebox{\columnwidth}{!}{\begin{tabular}{@{}lccc@{}}
\toprule
Quantity & earlier values & emulated, low & emulated, high\\
\midrule
""" + "\n".join(lines) + r"""
\bottomrule
\end{tabular}}

\vspace{1mm}\raggedright\footnotesize
Earlier values: 28.62~ms (ESP32) and 4.20~ms (Pi~4) per scalar multiplication, from the authors' previous platform runs; emulated: Table~\ref{tab:platform}. BLAKE2s 0.0174~ms and AES-GCM 0.075~ms on ESP32. Radio energy is evaluated in ns-3 (Section~\ref{subsec:ns3results}).
\end{table}
""")
