"""Dashboard Streamlit di IPB Extreme (prototipo di ricerca, non consulenza finanziaria).

Avvio:  streamlit run app.py
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ipb import pipeline
from ipb.config import DEFAULT, MARKETS, version_info
from ipb.data import DataError

st.set_page_config(page_title="IPB Extreme", page_icon="📈", layout="wide")
st.title("IPB Extreme")
st.caption("Prototipo quantitativo sperimentale — non è consulenza finanziaria. Nessun ordine viene inviato.")

with st.sidebar:
    st.header("Configurazione")
    market_name = st.selectbox("Mercato", list(MARKETS.keys()), index=0)
    start_date = st.date_input("Storico dal", value=date.today() - timedelta(days=365 * 20))
    horizon = st.selectbox("Orizzonte (sedute)", list(DEFAULT.horizons), index=1)
    threshold_pct = st.slider("Soglia rialzo/ribasso del target (%)", 0.5, 5.0, DEFAULT.default_threshold * 100, 0.25)
    cost_bps = st.slider("Costo per cambio posizione (bps)", 0, 30, int(DEFAULT.default_cost_bps))
    with_sens = st.checkbox("Analisi di sensibilità (più lenta)", value=False)
    run = st.button("Scarica dati e calcola", type="primary")

if "result" not in st.session_state:
    st.session_state.result = None

if run:
    with st.spinner("Scaricamento e calcolo walk-forward: può richiedere qualche decina di secondi..."):
        try:
            st.session_state.result = pipeline.run(market_name, start_date.isoformat(), horizon=horizon,
                                                   threshold=threshold_pct / 100, cost_bps=cost_bps,
                                                   with_sensitivity=with_sens)
        except DataError as e:
            st.session_state.result = None
            st.error(f"Dati non disponibili: {e}")
            st.info("Nessun dato simulato viene mostrato. Verificare connessione, ticker e provider.")
            st.stop()
        except Exception as e:  # errore di calcolo: mostrato, mai nascosto
            st.session_state.result = None
            st.error(f"Calcolo non riuscito: {type(e).__name__}: {e}")
            st.stop()

r = st.session_state.result
if r is None:
    st.info("Scegli i parametri e premi **Scarica dati e calcola**.")
    st.markdown("""
**Cosa calcola**
- **Pressure Score (IPB)**, -100/+100: pressione rialzista o ribassista (momentum, trend, partecipazione proxy, volume proxy, sentiment di volatilità).
- **Expectation Gap**, -100/+100: volatilità attesa contro realizzata (serve un indice di volatilità).
- **Reaction Anomaly**, -100/+100: reazione del prezzo diversa da quella implicita nel contesto.
- **Crowding & Fragility**, 0-100: posizionamento affollato e fragilità del trend. Punteggio euristico.
- **Rischio inversione**, 0-100: punteggio euristico, **non** una probabilità.
- **Probabilità** di rialzo/laterale/ribasso e di inversione: walk-forward, calibrate solo su dati passati, mostrate solo se battono la frequenza storica.
""")
    st.stop()

s = r.summary()
if s["data"]["synthetic"]:
    st.warning("DATI SINTETICI — SOLO TEST: nessun risultato di questa pagina riguarda un mercato reale.")
for w in r.warnings:
    st.warning(w)

lt = s["latest"]
fmt = lambda v, f="{:+.0f}": "N/D" if v is None else f.format(v)  # noqa: E731
c = st.columns(5)
c[0].metric("IPB / Pressure", fmt(lt["ipb"], "{:+.1f}"), lt["pressure"])
c[1].metric("Expectation Gap", fmt(lt["expectation_gap"]))
c[2].metric("Reaction Anomaly", fmt(lt["reaction_anomaly"]), lt.get("reaction_source") or "")
c[3].metric("Crowding & Fragility", fmt(lt["crowding_fragility"], "{:.0f}"), "euristico")
c[4].metric("Rischio inversione", fmt(lt["reversal_risk_score"], "{:.0f}"), "euristico, non probabilità")
st.caption(f"Ultima seduta {lt['date']} · {r.market} · sentiment da {lt.get('sentiment_source')}")

st.subheader(f"Probabilità a {r.horizon} sedute (soglia ±{r.threshold:.1%})")
for title, key, ev in (("Direzione", "probabilities_direction", s["evaluation_direction"]),
                       ("Inversione del trend a 20 sedute", "probabilities_reversal", s["evaluation_reversal"])):
    pv = lt[key]
    st.markdown(f"**{title}** — fonte: {pv['source']}")
    if pv["values"]:
        cols = st.columns(len(pv["values"]))
        for col, (lab, val) in zip(cols, pv["values"].items()):
            col.metric(lab, f"{val:.1%}")
    else:
        st.write("Non disponibile.")
    if "brier" in ev:
        st.caption(f"Fuori campione {ev['first']} → {ev['last']}, {ev['independent_periods']:.0f} periodi indipendenti: "
                   f"BSS vs frequenza storica {ev['bss']:+.2%}, BSS vs benchmark volatilità+trend "
                   f"{ev.get('bss_vs_simple_benchmark', float('nan')):+.2%}, log-loss {ev['log_loss']:.4f} "
                   f"(storica {ev['log_loss_climatology']:.4f}), ECE max {ev['ece_max']:.1%}. {ev['status']}.")
    else:
        st.caption(ev.get("status", ""))

with st.expander("Calibrazione e sottoperiodi (direzione)"):
    ev = s["evaluation_direction"]
    if ev.get("subperiods"):
        st.dataframe(pd.DataFrame(ev["subperiods"]), width="stretch", hide_index=True)
    for name, rows in (ev.get("calibration_bins") or {}).items():
        if rows:
            st.markdown(f"`{name}` — bin con almeno {DEFAULT.min_bin_count} osservazioni")
            st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

f = r.frame
st.subheader("Punteggi nel tempo")
fig = go.Figure()
for col, name in (("ipb", "IPB / Pressure"), ("expectation_gap", "Expectation Gap"),
                  ("reaction_anomaly", "Reaction Anomaly")):
    if f[col].notna().any():
        fig.add_trace(go.Scatter(x=f.index, y=f[col], name=name, line=dict(width=1.2)))
fig.add_hline(y=DEFAULT.pressure_band, line_dash="dash", opacity=.4)
fig.add_hline(y=-DEFAULT.pressure_band, line_dash="dash", opacity=.4)
fig.update_layout(height=360, margin=dict(l=20, r=20, t=20, b=20), yaxis_title="-100 / +100")
st.plotly_chart(fig, width="stretch")

fig2 = go.Figure()
fig2.add_trace(go.Scatter(x=f.index, y=f["crowding_fragility"], name="Crowding & Fragility"))
fig2.add_trace(go.Scatter(x=f.index, y=f["reversal_risk"], name="Rischio inversione (euristico)"))
fig2.update_layout(height=280, margin=dict(l=20, r=20, t=20, b=20), yaxis_title="0–100")
st.plotly_chart(fig2, width="stretch")

st.subheader("Backtest")
bi = r.bt_info
st.caption(f"Finestra comune {bi['start']} → {bi['end']} · costo {bi['cost_bps']} bps per cambio posizione · "
           f"esecuzione dopo {bi['execution_lag']} seduta/e. Risultati storici simulati, non previsioni.")
m = r.bt_metrics.copy()
for col in ["total_return", "annualized_return", "volatility", "max_drawdown", "time_in_market"]:
    m[col] = m[col].map(lambda x: f"{x:.1%}" if pd.notna(x) else "N/D")
m["sharpe_rf0"] = r.bt_metrics["sharpe_rf0"].map(lambda x: f"{x:.2f}" if pd.notna(x) else "N/D")
st.dataframe(m, width="stretch", hide_index=True)
with st.expander("Ipotesi di esecuzione e sottoperiodi"):
    for n in bi["execution_notes"]:
        st.write("- " + n)
    st.dataframe(pd.DataFrame(bi["subperiods"]), width="stretch", hide_index=True)

eq = pd.DataFrame(index=f.index)
for label, col in [("IPB long/flat", "strategy_return"), ("IPB + probabilità", "strategy_prob_return"),
                   ("Momentum MA100", "momentum_return"), ("Buy & hold", "buy_hold_return")]:
    if col in f:
        eq[label] = (1 + f[col].fillna(0)).cumprod().where(f[col].notna())
fig3 = go.Figure()
for col in eq:
    fig3.add_trace(go.Scatter(x=eq.index, y=eq[col], name=col))
fig3.update_layout(height=360, yaxis_title="Capitale iniziale = 1", margin=dict(l=20, r=20, t=20, b=20))
st.plotly_chart(fig3, width="stretch")

if r.sensitivity_prob is not None:
    st.subheader("Sensibilità")
    st.markdown("**Probabilità: orizzonti e soglie**")
    st.dataframe(r.sensitivity_prob, width="stretch", hide_index=True)
    st.markdown("**Backtest: costi, soglia IPB e ritardo di esecuzione**")
    st.dataframe(r.sensitivity_bt, width="stretch", hide_index=True)

st.subheader("Dati ed export")
cols = ["close", "ipb", "expectation_gap", "reaction_anomaly", "crowding_fragility", "reversal_risk",
        "p_down", "p_flat", "p_up", "p_rev"]
st.dataframe(f.reindex(columns=cols).tail(20), width="stretch")
st.download_button("Scarica risultati CSV", data=f.to_csv(index=True).encode("utf-8"),
                   file_name="ipb_extreme_results.csv", mime="text/csv")
import json  # noqa: E402
st.download_button("Scarica metriche JSON", data=json.dumps(s, ensure_ascii=False, indent=2).encode("utf-8"),
                   file_name="ipb_extreme_metrics.json", mime="application/json")
st.caption(f"Versioni: feature {version_info()['feature_version']}, modello {version_info()['model_version']}, "
           f"impostazioni {version_info()['settings_hash']}")
