"""
Traffic Simulation Unified Dashboard

Single simulation auto-runs on app start. All tabs share the same data:
- 🚗 Traffic UI: Animated intersection visualization (Play/Pause)
- 🧠 ML Ingress: Real-time ML analytics on the same data
- 📊 Analytics: Statistical analysis and predictions
- 📋 Data Explorer: Raw data, export
- ℹ️ About: Documentation

Usage: streamlit run app.py
"""
import streamlit as st
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import random
from collections import Counter

from engine.models import VehicleType, VEHICLE_PROFILES
from engine.intersection import Intersection, Direction
from engine.analytics import (
    TrafficStats, fit_arrival_distribution, predict_queue,
    compute_fundamental_diagram, recommend_green_time,
)
from engine.ingress import SyncIngressEngine

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Traffic Simulation",
    page_icon="🚦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Sidebar simulation parameters (changing these re-runs the sim)
# ---------------------------------------------------------------------------
st.sidebar.title("🚦 Simulation Controls")

spawn_rate = st.sidebar.slider("Spawn rate (veh/sec)", 0.5, 5.0, 2.5, 0.5)
sim_duration = st.sidebar.slider("Duration (seconds)", 30, 180, 90, 10)

st.sidebar.header("Vehicle Distribution")
pct_two_wheeler = st.sidebar.slider("Two-wheelers %", 0, 100, 45)
pct_auto = st.sidebar.slider("Auto-rickshaws %", 0, 100, 20)
pct_sedan = st.sidebar.slider("Sedans/Cars %", 0, 100, 25)
pct_truck = st.sidebar.slider("Heavy trucks %", 0, 100, 10)
total_pct = pct_two_wheeler + pct_auto + pct_sedan + pct_truck or 1
weights = [pct_two_wheeler/total_pct, pct_auto/total_pct,
           pct_sedan/total_pct, pct_truck/total_pct]

st.sidebar.header("Intersection")
arm_length = st.sidebar.slider("Arm length (m)", 100, 500, 300, 50)
min_green = st.sidebar.slider("Min green (s)", 5, 30, 15, 5)
max_green = st.sidebar.slider("Max green (s)", 30, 90, 60, 5)

st.sidebar.header("ML Settings")
anomaly_sigma = st.sidebar.slider("Anomaly threshold (σ)", 1.0, 4.0, 2.0, 0.5)


# ---------------------------------------------------------------------------
# Core: Run simulation ONCE (cached on parameters)
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner="Running simulation...")
def run_unified_simulation(
    _spawn_rate, _duration, _weights, _arm_length, _min_green, _max_green,
    _anomaly_sigma, _seed=42,
):
    """
    Single simulation run that produces ALL data for every tab:
    - Animation frames (for Traffic UI)
    - ML results (for ML Ingress tab)
    - Time-series DataFrame (for Analytics/Explorer)
    - Analytics summaries
    """
    random.seed(_seed)
    np.random.seed(_seed)

    # Initialize engine
    intersection = Intersection(arm_length=_arm_length, dt=0.1)
    intersection.controller.min_green = _min_green
    intersection.controller.max_green = _max_green

    # ML ingress engine
    ingress = SyncIngressEngine()
    ingress.ml_engine.anomaly_detector.threshold_sigma = _anomaly_sigma

    # Analytics stats
    stats = TrafficStats()

    vehicle_types = [VehicleType.TWO_WHEELER, VehicleType.AUTO_RICKSHAW,
                     VehicleType.SEDAN, VehicleType.HEAVY_TRUCK]
    directions = list(Direction)

    # Output collectors
    frames = []          # for animation
    ml_results = []      # ML ingress output per second
    time_series = []     # tabular data per second

    steps = int(_duration / intersection.dt)
    sample_interval = int(1.0 / intersection.dt)  # 1Hz
    frame_interval = 5  # capture every 5 steps for smooth animation
    prev_departed = 0

    for step_i in range(steps):
        # Spawn vehicles per arm
        for d in directions:
            if random.random() < _spawn_rate * intersection.dt * 0.5:
                vt = random.choices(vehicle_types, weights=_weights, k=1)[0]
                intersection.spawn_vehicle(d, vt)
                stats.record_arrival(intersection.time)

        # Step physics
        state = intersection.step()

        # Capture animation frame
        if step_i % frame_interval == 0:
            frames.append(state)

        # 1Hz sampling: ML + analytics + time series
        if step_i % sample_interval == 0:
            all_speeds = [v["speed"] for v in state.get("vehicles", [])]
            avg_speed = float(np.mean(all_speeds)) if all_speeds else 0.0

            # Feed ML ingress
            ml_result = ingress.process(
                queue_lengths=state.get("counts", {}),
                avg_speed=avg_speed,
                vehicles=state.get("vehicles", []),
                total_departed=state.get("total_departed", 0),
                sim_time=state.get("time", 0),
            )
            ml_results.append(ml_result)

            # Feed analytics stats
            stats.record(state["counts"], state["total_departed"], avg_speed, intersection.time)

            # Time series row
            time_series.append({
                "time": round(intersection.time, 1),
                "north": state["counts"]["north"],
                "south": state["counts"]["south"],
                "east": state["counts"]["east"],
                "west": state["counts"]["west"],
                "total_vehicles": sum(state["counts"].values()),
                "departed": state["total_departed"],
                "new_departures": state["total_departed"] - prev_departed,
                "avg_speed_kmh": round(avg_speed * 3.6, 1),
                "cycles": state["cycles"],
            })
            prev_departed = state["total_departed"]

    # Final analytics computations
    arrival_dist = fit_arrival_distribution(stats)
    queue_pred = predict_queue(stats)
    fundamental = compute_fundamental_diagram(stats)
    green_rec = recommend_green_time(stats)
    ml_summary = ingress.get_summary()

    df = pd.DataFrame(time_series)

    return {
        "frames": frames,
        "ml_results": ml_results,
        "ml_summary": ml_summary,
        "df": df,
        "arrival_dist": arrival_dist,
        "queue_pred": queue_pred,
        "fundamental": fundamental,
        "green_rec": green_rec,
    }


# ---------------------------------------------------------------------------
# Auto-run simulation (runs on first load, re-runs when params change)
# ---------------------------------------------------------------------------
data = run_unified_simulation(
    spawn_rate, sim_duration, weights, arm_length,
    min_green, max_green, anomaly_sigma,
)

frames = data["frames"]
ml_results = data["ml_results"]
ml_summary = data["ml_summary"]
df = data["df"]
arrival_dist = data["arrival_dist"]
queue_pred = data["queue_pred"]
fundamental = data["fundamental"]
green_rec = data["green_rec"]

# ---------------------------------------------------------------------------
# Title + KPI row
# ---------------------------------------------------------------------------
st.title("🚦 Indian Traffic Microsimulation")
st.caption("IDM + MOBIL + Adaptive Signals • Same data feeds all tabs")

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Total Departed", df["departed"].iloc[-1])
k2.metric("Peak Vehicles", df["total_vehicles"].max())
k3.metric("Avg Speed", f"{df['avg_speed_kmh'].mean():.1f} km/h")
last_ml = ml_results[-1] if ml_results else {}
los = last_ml.get("traffic_state", {}).get("los", "?")
k4.metric("LOS Grade", los)
k5.metric("Anomalies", ml_summary.get("anomalies_detected", 0))

# ---------------------------------------------------------------------------
# Tabs all sharing the same data
# ---------------------------------------------------------------------------
tab_traffic, tab_ml, tab_analytics, tab_explorer, tab_about = st.tabs([
    "🚗 Traffic UI", "🧠 ML Ingress", "📊 Analytics", "📋 Data Explorer", "ℹ️ About"
])


# ===========================================================================
# TAB: Traffic UI (animated visualization Play/Pause here)
# ===========================================================================
VEHICLE_COLORS = {"two_wheeler":"#FFD54F","auto_rickshaw":"#66BB6A","sedan":"#42A5F5","heavy_truck":"#EF5350"}
VEHICLE_SIZES = {"two_wheeler":6,"auto_rickshaw":9,"sedan":12,"heavy_truck":18}


def map_pos(direction, x, y, arm_len, center=300):
    road_w = 80
    scale = (center - road_w/2) / arm_len
    dist = (arm_len - x) * scale + road_w/2
    lat = ((y/7.0) - 0.5) * road_w
    if direction == "north": return center+lat, center-dist
    elif direction == "south": return center-lat, center+dist
    elif direction == "east": return center+dist, center+lat
    elif direction == "west": return center-dist, center-lat
    return center, center


def extract_veh(state, arm_len, center=300, sz=600):
    xs, ys, cols, sizes, txts = [], [], [], [], []
    for v in state.get("vehicles", []):
        vt = v.get("type","sedan")
        vx, vy = map_pos(v["direction"], v["x"], v["y"], arm_len, center)
        if 0 <= vx <= sz and 0 <= vy <= sz:
            xs.append(vx); ys.append(vy)
            cols.append(VEHICLE_COLORS.get(vt,"#FFF"))
            sizes.append(VEHICLE_SIZES.get(vt,8))
            txts.append(f"{vt}|{v['speed']:.1f}m/s|{v['direction']}")
    return xs, ys, cols, sizes, txts


with tab_traffic:
    st.subheader("4-Way Intersection Animated")
    st.caption("Press ▶ Play to see vehicles move. Same simulation data as ML tab.")

    # Sample frames for performance
    max_anim = min(len(frames), 150)
    step_sz = max(1, len(frames) // max_anim)
    sampled = frames[::step_sz]

    cs = 600; ctr = 300; rw = 80
    first = sampled[0]
    xs, ys, cols, sizes, txts = extract_veh(first, arm_length, ctr, cs)

    fig_anim = go.Figure(
        data=[go.Scatter(x=xs, y=ys, mode="markers",
              marker=dict(size=sizes, color=cols, symbol="square", opacity=0.9, line=dict(width=0)),
              hovertext=txts, hoverinfo="text", showlegend=False)],
        layout=go.Layout(
            width=620, height=620,
            plot_bgcolor="#0a0a0a", paper_bgcolor="#121212",
            xaxis=dict(range=[0,cs], showgrid=False, zeroline=False, showticklabels=False, fixedrange=True),
            yaxis=dict(range=[0,cs], showgrid=False, zeroline=False, showticklabels=False, fixedrange=True, scaleanchor="x"),
            margin=dict(l=5,r=5,t=40,b=5),
            title=dict(text=f"Traffic Animation • {len(sampled)} frames • {sim_duration}s", font=dict(color="#aaa",size=12)),
            updatemenus=[dict(type="buttons", showactive=False, y=1.06, x=0.5, xanchor="center",
                buttons=[
                    dict(label="▶ Play", method="animate",
                         args=[None, {"frame":{"duration":80,"redraw":True},"fromcurrent":True,"transition":{"duration":30}}]),
                    dict(label="⏸ Pause", method="animate",
                         args=[[None], {"frame":{"duration":0,"redraw":False},"mode":"immediate","transition":{"duration":0}}]),
                ])],
            sliders=[dict(active=0,
                steps=[dict(args=[[f"f{i}"],{"frame":{"duration":80,"redraw":True},"mode":"immediate","transition":{"duration":30}}],
                            label=f"{sampled[i].get('time',0):.0f}s", method="animate")
                       for i in range(0, len(sampled), max(1, len(sampled)//20))],
                x=0.05, len=0.9, y=-0.02,
                currentvalue=dict(prefix="Time: ", font=dict(color="#aaa",size=10)),
                font=dict(color="#888",size=9), tickcolor="#555", bordercolor="#555")],
        )
    )

    # Build animation frames
    anim_frames = []
    for i, state in enumerate(sampled):
        vd = extract_veh(state, arm_length, ctr, cs)
        anim_frames.append(go.Frame(
            data=[go.Scatter(x=vd[0], y=vd[1], mode="markers",
                  marker=dict(size=vd[3], color=vd[2], symbol="square", opacity=0.9, line=dict(width=0)),
                  hovertext=vd[4], hoverinfo="text", showlegend=False)],
            name=f"f{i}",
            layout=go.Layout(title=dict(
                text=f"t={state.get('time',0):.1f}s • Veh:{sum(state.get('counts',{}).values())} • Dep:{state.get('total_departed',0)}",
                font=dict(color="#aaa",size=12)))
        ))
    fig_anim.frames = anim_frames

    # Road shapes
    fig_anim.add_shape(type="rect", x0=ctr-rw/2, y0=0, x1=ctr+rw/2, y1=cs, fillcolor="#1a1a2e", line_width=0, layer="below")
    fig_anim.add_shape(type="rect", x0=0, y0=ctr-rw/2, x1=cs, y1=ctr+rw/2, fillcolor="#1a1a2e", line_width=0, layer="below")
    fig_anim.add_shape(type="rect", x0=ctr-rw/2, y0=ctr-rw/2, x1=ctr+rw/2, y1=ctr+rw/2, fillcolor="#252540", line_width=0, layer="below")
    for x0,y0,x1,y1 in [(ctr-rw/2,ctr-rw/2,ctr+rw/2,ctr-rw/2),(ctr-rw/2,ctr+rw/2,ctr+rw/2,ctr+rw/2),
                         (ctr-rw/2,ctr-rw/2,ctr-rw/2,ctr+rw/2),(ctr+rw/2,ctr-rw/2,ctr+rw/2,ctr+rw/2)]:
        fig_anim.add_shape(type="line", x0=x0, y0=y0, x1=x1, y1=y1, line=dict(color="#555",width=2), layer="below")
    for x0,y0,x1,y1 in [(ctr,0,ctr,ctr-rw/2),(ctr,ctr+rw/2,ctr,cs),(0,ctr,ctr-rw/2,ctr),(ctr+rw/2,ctr,cs,ctr)]:
        fig_anim.add_shape(type="line", x0=x0, y0=y0, x1=x1, y1=y1, line=dict(color="#333",width=1,dash="dash"), layer="below")

    st.plotly_chart(fig_anim, use_container_width=True)

    # Quick stats below animation
    last_f = frames[-1]
    lc1, lc2, lc3, lc4 = st.columns(4)
    lights = last_f.get("lights", {})
    counts = last_f.get("counts", {})
    for col, (d, em) in zip([lc1,lc2,lc3,lc4], [("north","⬆️"),("south","⬇️"),("east","➡️"),("west","⬅️")]):
        le = {"green":"🟢","red":"🔴","yellow":"🟡"}.get(lights.get(d,"red"),"⚪")
        col.metric(f"{em} {d.title()}", f"{counts.get(d,0)} veh", delta=f"{le} {lights.get(d,'').upper()}")


# ===========================================================================
# TAB: ML Ingress (same data, ML analytics)
# ===========================================================================
with tab_ml:
    st.subheader("🧠 ML Data Ingress Engine")
    st.caption(f"Processing the same {len(ml_results)} samples from the simulation above")

    # Summary metrics
    m1, m2, m3, m4 = st.columns(4)
    ts_data = last_ml.get("traffic_state", {})
    m1.metric("LOS", f"{ts_data.get('los','?')} {ts_data.get('description','')[:30]}")
    m2.metric("Density", f"{ts_data.get('density_pcu_km',0)} PCU/km")
    sp = last_ml.get("speed_prediction", {})
    m3.metric("Speed Forecast", f"{sp.get('predicted_speed_kmh',0)} km/h ({sp.get('trend','?')})")
    cong = last_ml.get("congestion", {})
    m4.metric("Congestion", f"{cong.get('congestion_index',0):.3f}")

    # ML detail tabs
    ml_tab1, ml_tab2, ml_tab3, ml_tab4, ml_tab5 = st.tabs([
        "🚨 Anomalies", "🚦 LOS", "📈 Speed", "🗺️ Congestion", "⚡ Optimizer"
    ])
    timestamps = [r["timestamp"] for r in ml_results]

    with ml_tab1:
        scores = [r.get("anomaly",{}).get("score",0) for r in ml_results]
        is_anom = [r.get("anomaly",{}).get("is_anomaly",False) for r in ml_results]
        fig_a = go.Figure()
        fig_a.add_trace(go.Scatter(x=timestamps, y=scores, mode="lines", name="Score", line=dict(color="#BB86FC")))
        fig_a.add_hline(y=anomaly_sigma, line_dash="dash", line_color="#CF6679", annotation_text=f"Threshold ({anomaly_sigma}σ)")
        ax = [t for t,a in zip(timestamps, is_anom) if a]
        ay = [s for s,a in zip(scores, is_anom) if a]
        if ax:
            fig_a.add_trace(go.Scatter(x=ax, y=ay, mode="markers", name="Anomaly", marker=dict(color="#F44336",size=10,symbol="x")))
        fig_a.update_layout(height=300, template="plotly_dark", xaxis_title="Time (s)", yaxis_title="Score")
        st.plotly_chart(fig_a, use_container_width=True)
        recent = ml_summary.get("recent_anomalies", [])
        if recent:
            st.dataframe(pd.DataFrame(recent), hide_index=True, use_container_width=True)

    with ml_tab2:
        densities = [r.get("traffic_state",{}).get("density_pcu_km",0) for r in ml_results]
        vc = [r.get("traffic_state",{}).get("v_c_ratio",0) for r in ml_results]
        fig_l = make_subplots(rows=2, cols=1, subplot_titles=("PCU Density","V/C Ratio"), shared_xaxes=True)
        fig_l.add_trace(go.Scatter(x=timestamps, y=densities, mode="lines", line=dict(color="#03DAC6")), row=1, col=1)
        fig_l.add_trace(go.Scatter(x=timestamps, y=vc, mode="lines", line=dict(color="#FF9800")), row=2, col=1)
        fig_l.add_hline(y=1.0, line_dash="dash", line_color="#F44336", row=2, col=1)
        fig_l.update_layout(height=400, template="plotly_dark", showlegend=False)
        st.plotly_chart(fig_l, use_container_width=True)

        los_grades = [r.get("traffic_state",{}).get("los","?") for r in ml_results]
        gc = Counter(los_grades)
        fig_pie = px.pie(values=list(gc.values()), names=list(gc.keys()),
                         color_discrete_map={"A":"#4CAF50","B":"#8BC34A","C":"#FFEB3B","D":"#FF9800","E":"#F44336","F":"#9C27B0"})
        fig_pie.update_layout(height=250, template="plotly_dark", title="LOS Distribution")
        st.plotly_chart(fig_pie, use_container_width=True)

    with ml_tab3:
        cur_spd = [r.get("speed_prediction",{}).get("current_speed_kmh",0) for r in ml_results]
        pred_spd = [r.get("speed_prediction",{}).get("predicted_speed_kmh",0) for r in ml_results]
        fig_s = go.Figure()
        fig_s.add_trace(go.Scatter(x=timestamps, y=cur_spd, mode="lines", name="Current", line=dict(color="#42A5F5")))
        fig_s.add_trace(go.Scatter(x=timestamps, y=pred_spd, mode="lines", name="Predicted (+10s)", line=dict(color="#FF9800",dash="dash")))
        fig_s.update_layout(height=300, template="plotly_dark", xaxis_title="Time (s)", yaxis_title="km/h")
        st.plotly_chart(fig_s, use_container_width=True)

    with ml_tab4:
        ci = [r.get("congestion",{}).get("congestion_index",0) for r in ml_results]
        fig_c = go.Figure()
        fig_c.add_trace(go.Scatter(x=timestamps, y=ci, mode="lines+markers", marker=dict(size=3), line=dict(color="#EF5350")))
        fig_c.add_hline(y=0.5, line_dash="dash", line_color="#FF9800", annotation_text="High")
        fig_c.update_layout(height=300, template="plotly_dark", xaxis_title="Time (s)", yaxis_title="Index")
        st.plotly_chart(fig_c, use_container_width=True)
        hs = ml_results[-1].get("congestion",{}).get("hotspots",[])
        if hs:
            st.dataframe(pd.DataFrame(hs), hide_index=True, use_container_width=True)

    with ml_tab5:
        opt_data = [r.get("signal_optimization",{}) for r in ml_results if r.get("signal_optimization",{}).get("action")=="optimized"]
        if opt_data:
            ng=[d["green_times"]["north"] for d in opt_data]
            sg=[d["green_times"]["south"] for d in opt_data]
            eg=[d["green_times"]["east"] for d in opt_data]
            wg=[d["green_times"]["west"] for d in opt_data]
            ox=list(range(len(opt_data)))
            fig_o = go.Figure()
            fig_o.add_trace(go.Scatter(x=ox,y=ng,name="N",line=dict(color="#42A5F5")))
            fig_o.add_trace(go.Scatter(x=ox,y=sg,name="S",line=dict(color="#EF5350")))
            fig_o.add_trace(go.Scatter(x=ox,y=eg,name="E",line=dict(color="#66BB6A")))
            fig_o.add_trace(go.Scatter(x=ox,y=wg,name="W",line=dict(color="#FFD54F")))
            fig_o.update_layout(height=300, template="plotly_dark", xaxis_title="Step", yaxis_title="Green (s)")
            st.plotly_chart(fig_o, use_container_width=True)
        else:
            st.info("No optimization steps yet.")


# ===========================================================================
# TAB: Analytics (distribution fitting, queue prediction, fundamental diagram)
# ===========================================================================
with tab_analytics:
    st.subheader("📊 Statistical Analytics")

    # Vehicle counts over time
    fig_counts = px.area(df, x="time", y=["north","south","east","west"],
        labels={"value":"Vehicles","time":"Time (s)","variable":"Direction"},
        color_discrete_sequence=["#636EFA","#EF553B","#00CC96","#AB63FA"])
    fig_counts.update_layout(height=300, margin=dict(t=20,b=20))
    st.plotly_chart(fig_counts, use_container_width=True)

    col_a, col_b = st.columns(2)
    with col_a:
        fig_speed = px.line(df, x="time", y="avg_speed_kmh", labels={"avg_speed_kmh":"Speed (km/h)","time":"Time (s)"})
        fig_speed.update_layout(height=250, margin=dict(t=20,b=20), title="Average Speed")
        st.plotly_chart(fig_speed, use_container_width=True)
    with col_b:
        fig_dep = px.line(df, x="time", y="departed", labels={"departed":"Departed","time":"Time (s)"})
        fig_dep.update_layout(height=250, margin=dict(t=20,b=20), title="Cumulative Departures")
        st.plotly_chart(fig_dep, use_container_width=True)

    # Arrival distribution
    st.subheader("Arrival Distribution Fitting")
    if arrival_dist["best_fit"] != "insufficient_data":
        dc1, dc2, dc3 = st.columns(3)
        dc1.metric("Best Fit", arrival_dist["best_fit"].capitalize())
        dc2.metric("λ (arrivals/s)", arrival_dist["poisson_lambda"])
        dc3.metric("CV", arrival_dist["cv"])

    # Queue prediction
    st.subheader("Queue Prediction (30s)")
    pc = st.columns(4)
    for i, (direction, d) in enumerate(queue_pred.items()):
        emoji = {"increasing":"📈","decreasing":"📉","stable":"➡️"}.get(d.get("trend",""),"❓")
        pc[i].metric(direction.title(), f"{d.get('current',0)} → {d.get('predicted_30s','?')}", delta=f"{emoji} {d.get('trend','?')}")

    # Fundamental diagram
    if fundamental.get("points"):
        st.subheader("Fundamental Diagram")
        fd_df = pd.DataFrame(fundamental["points"])
        fig_fd = make_subplots(rows=1, cols=2, subplot_titles=("Flow vs Density","Speed vs Density"))
        fig_fd.add_trace(go.Scatter(x=fd_df["density"], y=fd_df["flow"], mode="markers",
                         marker=dict(color=fd_df["speed"], colorscale="Viridis", showscale=True)), row=1, col=1)
        fig_fd.add_trace(go.Scatter(x=fd_df["density"], y=fd_df["speed"], mode="markers+lines",
                         marker=dict(color="#EF553B")), row=1, col=2)
        fig_fd.update_layout(height=300, showlegend=False, margin=dict(t=40,b=20))
        st.plotly_chart(fig_fd, use_container_width=True)

    # Signal recommendation
    st.subheader("🚥 Signal Timing Recommendation")
    rc1, rc2, rc3 = st.columns(3)
    rc1.metric("N-S Green %", f"{green_rec['ns_pct']}%")
    rc2.metric("E-W Green %", f"{green_rec['ew_pct']}%")
    rc3.metric("Confidence", green_rec["confidence"].capitalize())


# ===========================================================================
# TAB: Data Explorer
# ===========================================================================
with tab_explorer:
    st.subheader("📋 Telemetry Data")
    st.dataframe(df, use_container_width=True, height=400)
    st.subheader("Summary")
    st.dataframe(df.describe(), use_container_width=True)
    csv = df.to_csv(index=False)
    st.download_button("💾 Download CSV", csv, "traffic_telemetry.csv", "text/csv", use_container_width=True)

    st.subheader("Custom Plot")
    y_cols = st.multiselect("Columns", [c for c in df.columns if c != "time"], default=["total_vehicles","avg_speed_kmh"])
    if y_cols:
        fig_custom = px.line(df, x="time", y=y_cols)
        fig_custom.update_layout(height=300, margin=dict(t=20,b=20))
        st.plotly_chart(fig_custom, use_container_width=True)


# ===========================================================================
# TAB: About
# ===========================================================================
with tab_about:
    st.markdown("""
    ### Architecture

    ```
    Simulation Engine (auto-runs on app start)
         │
         ├──→ Animation Frames ──→ 🚗 Traffic UI tab (Play/Pause)
         │
         ├──→ ML Ingress Engine ──→ 🧠 ML tab (anomaly, LOS, speed, congestion, optimizer)
         │
         └──→ Time-Series Data ──→ 📊 Analytics + 📋 Data Explorer tabs
    ```

    **One simulation. All tabs share the same data. No separate "Run" buttons.**

    ### Models

    | Model | Purpose |
    |-------|---------|
    | IDM | Car-following (vectorized NumPy) |
    | MOBIL | Lateral movement (Indian lane-splitting) |
    | Adaptive Controller | Webster's formula signal timing |
    | Anomaly Detection | Z-score + IQR |
    | LOS Classification | PCU density (INDO-HCM) |
    | Speed Prediction | Online linear regression |
    | Congestion Clustering | Density-based spatial cells |
    | Signal Optimizer | Online gradient descent |

    ### Vehicle Types

    | Type | Max Speed | Default % |
    |------|-----------|-----------|
    | 🏍️ Two-wheeler | 60 km/h | 45% |
    | 🛺 Auto-rickshaw | 40 km/h | 20% |
    | 🚗 Sedan/Car | 80 km/h | 25% |
    | 🚛 Heavy Truck | 60 km/h | 10% |

    ---
    Change parameters in the sidebar → simulation auto-reruns → all tabs update.
    """)
