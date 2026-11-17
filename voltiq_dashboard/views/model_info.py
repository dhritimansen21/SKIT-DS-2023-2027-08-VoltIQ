"""Model information panel (FR-17) with a placeholder retrain action (admin)."""
import plotly.graph_objects as go
import streamlit as st

import ui


def render(ctx):
    ui.page_header("Model Information", "Models in use, their versions and evaluation metrics.")
    p = ctx.provider
    info = p.get_model_info()
    st.caption("A dash (-) means no metric is available for that model yet. Add your trained models' metrics in models/model_info.csv.")

    for _, m in info.iterrows():
        with st.container(border=True):
            st.markdown(f"**{m['purpose']}** - {m['algorithm']} ({m['version']})")
            st.caption(f"Model id `{m['model_id']}` - trained {m['trained_at']:%d %b %Y} - {m['notes']}")
            cols = st.columns(5)
            def show(i, label, key, unit=""):
                v = m[key]
                with cols[i]:
                    ui.metric_card(label, "-" if v != v or v is None else (f"{v:.2f}" if key in ("precision", "recall", "f1") else f"{v:.1f}"), unit)
            show(0, "MAE", "mae", "W"); show(1, "RMSE", "rmse", "W")
            show(2, "Precision", "precision"); show(3, "Recall", "recall"); show(4, "F1-score", "f1")

    rows = info[info["purpose"].str.contains("Theft", na=False)]
    clf = rows.iloc[0] if len(rows) else None
    if clf is not None and clf[["precision", "recall", "f1"]].notna().all():
        fig = go.Figure(go.Bar(x=["Precision", "Recall", "F1-score"], y=[clf["precision"], clf["recall"], clf["f1"]],
                               marker_color=["#1F5FBF", "#F28C28", "#2E7D32"], text=[f"{clf[k]:.2f}" for k in ("precision", "recall", "f1")]))
        fig.update_layout(title="Theft class metrics (imbalanced data, SMOTE on training set)", height=300,
                          yaxis=dict(range=[0, 1]), template="plotly_white", margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig, width="stretch")

    st.subheader("Retrain / update models")
    if ctx.is_admin:
        if st.button("Retrain models", type="primary"):
            with st.spinner("Submitting retraining request..."):
                msg = p.request_retrain(ctx.user["username"])
            st.success(msg)
    else:
        st.info("Only an administrator can retrain or update models.")
