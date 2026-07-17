import os
import sys
import uuid
import json
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from openai import OpenAI
import time

# ==========================================
# CẤU HÌNH GIAO DIỆN MẶC ĐỊNH 
# ==========================================
st.set_page_config(page_title="OPC Mission Control", page_icon="⚡", layout="wide")

st.markdown("""
    <style>
        .block-container { padding-top: 2rem; padding-bottom: 1rem; }
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-thumb { background: #ff4b4b; border-radius: 10px; }
        ::-webkit-scrollbar-track { background: transparent; }
        .stTabs [data-baseweb="tab-list"] { gap: 8px; }
        .stTabs [data-baseweb="tab"] { padding: 10px 20px; background-color: #1e1e2d; border-radius: 5px 5px 0 0; }
        .stTabs [aria-selected="true"] { background-color: #ff4b4b !important; color: white !important; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# KẾT NỐI OPENAI
# ==========================================
try:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
except Exception as e:
    st.error("🚨 Không tìm thấy API Key trong Secrets!")
    st.stop()

# ==========================================
# CÁC HÀM XỬ LÝ DỮ LIỆU & LOGIC AI 
# ==========================================
def format_currency(val):
    try:
        v = float(val)
        sign = "-" if v < 0 else ""
        abs_v = abs(v)
        if abs_v >= 1_000_000_000: return f"{sign}{abs_v/1_000_000_000:.2f} tỷ"
        elif abs_v >= 1_000_000: return f"{sign}{abs_v/1_000_000:.0f} triệu"
        else: return f"{sign}{abs_v:.0f}"
    except: return str(val)

@st.cache_data
def layer4_data_ingestion(uploaded_file):
    return {
        "contracts": pd.read_excel(uploaded_file, sheet_name='04_CONTRACTS').to_string(index=False),
        "cashflow": pd.read_excel(uploaded_file, sheet_name='09_CASHFLOW').to_string(index=False),
        "txn": pd.read_excel(uploaded_file, sheet_name='08_BANK_TXN').to_string(index=False),
        "rules": pd.read_excel(uploaded_file, sheet_name='13_RISK_RULES').to_string(index=False),
        "bank_prod": pd.read_excel(uploaded_file, sheet_name='11_BANK_PRODUCTS').to_string(index=False)
    }

def agent_planner(data_bundle):
    response = client.chat.completions.create(
        model="gpt-4o", response_format={ "type": "json_object" }, 
        messages=[{"role": "system", "content": "Trả về JSON: { 'task_breakdown': '...', 'approval_gates': '...', 'workflow_plan': '...' } Tiếng Việt."}, {"role": "user", "content": data_bundle['contracts']}], temperature=0.1
    )
    parsed = json.loads(response.choices[0].message.content)
    return f"**Mục tiêu:** {parsed.get('task_breakdown', '')}\n\n**Workflow:** {parsed.get('workflow_plan', '')}"

def agent_finance(data_bundle):
    response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": "Tóm tắt ngắn 2 đoạn: Phân tích hụt vốn & Đề xuất giải pháp. Tiếng Việt."}, {"role": "user", "content": data_bundle['cashflow']}], temperature=0.1)
    return response.choices[0].message.content

def agent_risk_compliance(data_bundle):
    response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": "Phân tích rủi ro ngắn gọn. Báo cáo giao dịch >= 85 điểm. Tiếng Việt."}, {"role": "user", "content": f"Data: {data_bundle['txn']}"}], temperature=0.1)
    return response.choices[0].message.content

def agent_banking_integration(data_bundle):
    response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": "Gợi ý 1 ngân hàng tốt nhất. Rất ngắn gọn. Tiếng Việt."}, {"role": "user", "content": data_bundle['bank_prod']}], temperature=0.1)
    return response.choices[0].message.content

def agent_decision(full_packet):
    response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": "Đóng vai Tổng Giám Đốc. Phán quyết DUYỆT hoặc TỪ CHỐI dựa trên dữ liệu. Trình bày max 4 câu sắc bén. Kèm Confidence Score %."}, {"role": "user", "content": full_packet}], temperature=0.1)
    return response.choices[0].message.content

# ==========================================
# GIAO DIỆN CHÍNH (ĐIỀU HƯỚNG BẰNG TABS)
# ==========================================
def main():
    col1, col2 = st.columns([3, 1])
    with col1:
        st.title("⚡ OPC Multi-Agent Command Center")
    with col2:
        uploaded_file = st.file_uploader("Nạp Data (Excel)", type=["xlsx"], label_visibility="collapsed")

    if uploaded_file is None:
        st.info("👈 Vui lòng tải file dữ liệu lên để kích hoạt hệ thống.")
        return

    # Load data
    raw_data = layer4_data_ingestion(uploaded_file)
    df_cf = pd.read_excel(uploaded_file, sheet_name='09_CASHFLOW')
    df_txn = pd.read_excel(uploaded_file, sheet_name='08_BANK_TXN')

    # Khởi tạo 4 Tabs chính theo yêu cầu Brainstorm
    tab_overview, tab_agents, tab_dashboard, tab_chat = st.tabs([
        "🌐 Overview", "🤖 Agents Fleet", "📊 Power Dashboard", "💬 Office & Chat"
    ])

    # ---------------------------------------------------------
    # TAB 1: OVERVIEW (Tổng quan hệ thống)
    # ---------------------------------------------------------
    with tab_overview:
        st.markdown("### 📡 System Overview")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Active Models", "gpt-4o / MinMax", "Online")
        m2.metric("Total Agents", "6 Specialists", "Running")
        m3.metric("Task Completion", "85%", "+12% speed")
        m4.metric("Tokens Remaining", "1,245,000", "Stable")
        
        st.divider()
        col_act, col_arch = st.columns([1, 1])
        
        with col_act:
            st.markdown("**🔄 Recent Activities & Task Progress**")
            st.progress(100, text="Planner Agent: Data Extracted (100%)")
            st.progress(80, text="Risk Agent: Scanning Transactions (80%)")
            st.progress(45, text="Finance Agent: Forecasting Cashflow (45%)")
            
        with col_arch:
            st.markdown("**🧠 Khung suy luận AI (Reasoning Architecture)**")
            st.info("""
            **Mô tả luồng dữ liệu:**
            1. **Input:** File Excel (Contracts, Cashflow, Bank Txn).
            2. **Orchestrator:** Phân dán luồng bằng Python Streamlit.
            3. **Agentic Layer:** Gọi API `gpt-4o` với Prompt kỹ thuật (System Prompts).
            4. **Output:** Structured JSON (Planner) & Quyết định nhị phân (Decision Agent).
            """)

    # ---------------------------------------------------------
    # TAB 2: AGENTS (Theo dõi từng Agent)
    # ---------------------------------------------------------
    with tab_agents:
        st.markdown("### 🤖 Agents Fleet Status")
        st.caption("Theo dõi trạng thái và khối lượng công việc của từng agent.")
        
        a1, a2, a3 = st.columns(3)
        with a1:
            st.success("**Planner Agent** (Online)\n\nĐã xử lý: 420 tasks\n\nContribute: 25%")
        with a2:
            st.warning("**Risk Agent** (Processing)\n\nĐã xử lý: 315 tasks\n\nContribute: 30%")
        with a3:
            st.info("**Finance Agent** (Standby)\n\nĐã xử lý: 150 tasks\n\nContribute: 15%")
            
        st.markdown("**🔥 Heatmap hoạt động (Mô phỏng)**")
        # Tạo Heatmap mô phỏng
        z = [[1, 20, 30, 50, 1], [20, 1, 60, 80, 30], [30, 60, 1, -10, 20]]
        fig_heat = go.Figure(data=go.Heatmap(z=z, colorscale='Reds'))
        fig_heat.update_layout(height=250, margin=dict(t=10, b=10, l=10, r=10), template="plotly_dark", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_heat, use_container_width=True)

    # ---------------------------------------------------------
    # TAB 3: POWER DASHBOARD (Chức năng cốt lõi)
    # ---------------------------------------------------------
    with tab_dashboard:
        # Chạy ngầm AI khi vào tab này
        with st.spinner("Đang tổng hợp dữ liệu thời gian thực..."):
            p_rep = agent_planner(raw_data)
            f_rep = agent_finance(raw_data)
            r_rep = agent_risk_compliance(raw_data)
            b_rep = agent_banking_integration(raw_data)
            final_decision = agent_decision(f"{p_rep}\n\n[TÀI CHÍNH]\n{f_rep}\n\n[RỦI RO]\n{r_rep}")

        st.markdown("### 📈 Analytics Dashboard")
        chart_col1, chart_col2 = st.columns(2)
        layout_update = dict(template="plotly_dark", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", margin=dict(l=10, r=10, t=30, b=10), height=280)

        with chart_col1:
            cash_col = df_cf.columns[-2]
            df_cf[cash_col] = pd.to_numeric(df_cf[cash_col].astype(str).str.replace(',', ''), errors='coerce')
            fig_cf = px.bar(df_cf, x=df_cf.columns[0], y=cash_col, title="📉 Dự phóng Dòng tiền (Cashflow)", color=cash_col, color_continuous_scale=['#ff4b4b', '#00cc96'])
            fig_cf.update_layout(**layout_update)
            st.plotly_chart(fig_cf, use_container_width=True)

        with chart_col2:
            risk_col = df_txn.columns[-1]
            df_txn[risk_col] = pd.to_numeric(df_txn[risk_col], errors='coerce')
            df_risk_top = df_txn.sort_values(by=risk_col, ascending=True).tail(5) 
            fig_bar = px.bar(df_risk_top, x=risk_col, y=df_txn.columns[0], orientation='h', title="🛡️ Top Giao dịch Rủi ro", color=risk_col, color_continuous_scale='Reds')
            fig_bar.update_layout(**layout_update)
            st.plotly_chart(fig_bar, use_container_width=True)

        st.markdown("### 🎯 Thẻ Quyết định (Decision Card)")
        st.error(final_decision)
        
        st.markdown("**Approval Gates:**")
        btn1, btn2 = st.columns(2)
        btn1.button("✅ DUYỆT (Approve)", use_container_width=True, type="primary")
        btn2.button("❌ TỪ CHỐI (Reject)", use_container_width=True)

    # ---------------------------------------------------------
    # TAB 4: CHAT & OFFICE (Tương tác trực tiếp)
    # ---------------------------------------------------------
    with tab_chat:
        st.markdown("### 💬 Agent Command Line")
        st.caption("Chat với từng con Agent hoặc phân loại task.")
        
        agent_select = st.selectbox("Chọn Agent để tương tác:", ["Master Orchestrator", "Planner Agent", "Finance Agent", "Risk Agent"])
        
        # Giao diện Chat mô phỏng
        chat_container = st.container(height=300)
        with chat_container:
            st.chat_message("assistant").write(f"Xin chào! Tôi là {agent_select}. Tôi đã sẵn sàng nhận task.")
            
        prompt = st.chat_input(f"Giao task cho {agent_select}...")
        if prompt:
            with chat_container:
                st.chat_message("user").write(prompt)
                st.chat_message("assistant").write("Đang xử lý yêu cầu... (Cần tích hợp API hội thoại tại đây)")

if __name__ == "__main__":
    main()
