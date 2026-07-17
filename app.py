import os
import sys
import uuid
import json
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from openai import OpenAI

# ==========================================
# CẤU HÌNH GIAO DIỆN MẶC ĐỊNH 
# ==========================================
st.set_page_config(page_title="OPC Mission Control", page_icon="⚡", layout="wide")

# CSS HACK: APPLE GLASSMORPHISM & DARK MODE
st.markdown("""
    <style>
        /* Hình nền cao cấp: Nền tối + Gradient phát sáng mờ ở 2 góc */
        .stApp {
            background: radial-gradient(circle at 10% 20%, rgba(59, 130, 246, 0.12), transparent 30%),
                        radial-gradient(circle at 90% 80%, rgba(255, 75, 75, 0.12), transparent 30%),
                        #0b0f19 !important;
            background-attachment: fixed;
        }

        .block-container { padding-top: 2rem; padding-bottom: 1rem; }
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.2); border-radius: 10px; }
        ::-webkit-scrollbar-track { background: transparent; }
        
        /* Glassmorphism cho khung Tabs */
        .stTabs [data-baseweb="tab-list"] { 
            gap: 10px; 
            border-bottom: none; 
            background: rgba(20, 20, 30, 0.4);
            padding: 10px 10px 0px 10px;
            border-radius: 15px 15px 0 0;
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid rgba(255,255,255,0.05);
        }
        .stTabs [data-baseweb="tab"] { 
            padding: 10px 20px; 
            background-color: transparent; 
            border-radius: 10px 10px 0 0; 
            color: #a1a1aa;
        }
        .stTabs [aria-selected="true"] { 
            background-color: rgba(255, 255, 255, 0.08) !important; 
            color: white !important; 
            border: 1px solid rgba(255,255,255,0.1);
            border-bottom: none;
            box-shadow: 0 -4px 20px rgba(0,0,0,0.3);
        }

        /* Glassmorphism cho Metrics */
        div[data-testid="metric-container"] { 
            background: rgba(255, 255, 255, 0.03); 
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid rgba(255, 255, 255, 0.08); 
            padding: 5% 10%; 
            border-radius: 16px; 
            box-shadow: 0 4px 30px rgba(0, 0, 0, 0.1);
        }

        /* Glassmorphism cho các hộp thoại Info/Error */
        .stAlert, .stInfo, .stSuccess, .stWarning, .stError {
            background: rgba(255, 255, 255, 0.05) !important;
            backdrop-filter: blur(10px) !important;
            border: 1px solid rgba(255, 255, 255, 0.08) !important;
            border-radius: 12px !important;
            color: #e4e4e7 !important;
        }
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
def layer4_data_ingestion(uploaded_file):
    return {
        "contracts": pd.read_excel(uploaded_file, sheet_name='04_CONTRACTS').to_string(index=False),
        "cashflow": pd.read_excel(uploaded_file, sheet_name='09_CASHFLOW').to_string(index=False),
        "txn": pd.read_excel(uploaded_file, sheet_name='08_BANK_TXN').to_string(index=False),
        "rules": pd.read_excel(uploaded_file, sheet_name='13_RISK_RULES').to_string(index=False),
        "bank_prod": pd.read_excel(uploaded_file, sheet_name='11_BANK_PRODUCTS').to_string(index=False)
    }

def agent_planner(data_bundle):
    response = client.chat.completions.create(model="gpt-4o", response_format={ "type": "json_object" }, messages=[{"role": "system", "content": "Trả về JSON: { 'task_breakdown': '...', 'approval_gates': '...', 'workflow_plan': '...' } Tiếng Việt."}, {"role": "user", "content": data_bundle['contracts']}], temperature=0.1)
    parsed = json.loads(response.choices[0].message.content)
    return f"**Mục tiêu:** {parsed.get('task_breakdown', '')}\n\n**Workflow:** {parsed.get('workflow_plan', '')}"
def agent_finance(data_bundle):
    return client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": "Tóm tắt ngắn 2 đoạn: Phân tích hụt vốn & Đề xuất giải pháp. Tiếng Việt."}, {"role": "user", "content": data_bundle['cashflow']}], temperature=0.1).choices[0].message.content
def agent_risk_compliance(data_bundle):
    return client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": "Phân tích rủi ro ngắn gọn. Báo cáo giao dịch >= 85 điểm. Tiếng Việt."}, {"role": "user", "content": f"Data: {data_bundle['txn']}"}], temperature=0.1).choices[0].message.content
def agent_banking_integration(data_bundle):
    return client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": "Gợi ý 1 ngân hàng tốt nhất. Rất ngắn gọn. Tiếng Việt."}, {"role": "user", "content": data_bundle['bank_prod']}], temperature=0.1).choices[0].message.content
def agent_decision(full_packet):
    return client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": "Đóng vai Tổng Giám Đốc. Phán quyết DUYỆT hoặc TỪ CHỐI. Trình bày max 4 câu sắc bén. Kèm Confidence Score %."}, {"role": "user", "content": full_packet}], temperature=0.1).choices[0].message.content

# ==========================================
# MAIN APP (UX LANDING PAGE -> DASHBOARD)
# ==========================================
def main():
    # 1. KIỂM TRA TRẠNG THÁI SESSION
    if "data_loaded" not in st.session_state:
        st.session_state.data_loaded = False

    # 2. GIAO DIỆN LANDING PAGE (CHƯA NẠP FILE)
    if not st.session_state.data_loaded:
        st.markdown("<br><br><br><br><br>", unsafe_allow_html=True)
        col_L, col_C, col_R = st.columns([1, 2, 1])
        with col_C:
            st.markdown("<h1 style='text-align: center; color: white; text-shadow: 0 0 20px rgba(59,130,246,0.5);'>⚡ OPC COMMAND CENTER</h1>", unsafe_allow_html=True)
            st.markdown("<p style='text-align: center; color: #a1a1aa; margin-bottom: 30px;'>Hệ thống Phân tích Đa Tác nhân AI (Multi-Agent System)</p>", unsafe_allow_html=True)
            
            uploaded_file = st.file_uploader("", type=["xlsx"])
            if uploaded_file is not None:
                with st.spinner("Đang trích xuất dữ liệu vào bộ nhớ đệm (RAM)..."):
                    st.session_state.raw_data = layer4_data_ingestion(uploaded_file)
                    st.session_state.df_cf = pd.read_excel(uploaded_file, sheet_name='09_CASHFLOW')
                    st.session_state.df_txn = pd.read_excel(uploaded_file, sheet_name='08_BANK_TXN')
                    st.session_state.data_loaded = True
                    st.rerun() # Tự động load lại trang để vào Dashboard
        st.stop() # Dừng chạy code bên dưới nếu chưa có file

    # ==========================================
    # 3. GIAO DIỆN CHÍNH (KHI ĐÃ NẠP FILE)
    # ==========================================
    raw_data = st.session_state.raw_data
    df_cf = st.session_state.df_cf
    df_txn = st.session_state.df_txn

    head_col1, head_col2 = st.columns([5, 1])
    with head_col1:
        st.markdown("## ⚡ OPC Multi-Agent Command Center")
    with head_col2:
        if st.button("🔄 Đóng & Nạp file mới", use_container_width=True):
            st.session_state.clear() # Xóa RAM
            st.rerun()

    # Khởi tạo 4 Tabs
    tab_overview, tab_agents, tab_dashboard, tab_chat = st.tabs([
        "🌐 Overview", "🤖 Agents Fleet", "📊 Power Dashboard", "💬 Office & Chat"
    ])

    # --- TAB 1: OVERVIEW ---
    with tab_overview:
        st.markdown("### 📡 Trung tâm Điều hành AI (System Overview)")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("LLM Engine", "gpt-4o", "Core API Online")
        m2.metric("Lực lượng Agent", "6 Chuyên gia", "Đang trực chiến")
        m3.metric("Tiến trình Task", "85% Hoàn thành", "Tốc độ xử lý +12%")
        m4.metric("Tài nguyên Token", "1,245,000", "Trong mức an toàn")
        st.divider()
        st.info("Hệ thống đã nhận diện luồng dữ liệu Excel. Sẵn sàng điều phối các Agent.")

    # --- TAB 2: AGENT FLEET ---
    with tab_agents:
        st.markdown("### 🤖 Báo cáo Năng lực Lực lượng (Agents Fleet Status)")
        a1, a2, a3 = st.columns(3)
        with a1: st.success("**🎯 Planner Agent**\n\n- Đã xử lý: 420 tasks\n- Đóng góp: 25%")
        with a2: st.warning("**🛡️ Risk Agent**\n\n- Đã xử lý: 315 tasks\n- Đóng góp: 30%")
        with a3: st.info("**📊 Finance Agent**\n\n- Đã xử lý: 150 tasks\n- Đóng góp: 15%")
        
        st.markdown("<br>", unsafe_allow_html=True)
        z = [[1, 20, 30, 50, 1], [20, 1, 60, 80, 30], [30, 60, 1, -10, 20]]
        fig_heat = go.Figure(data=go.Heatmap(z=z, x=['T2', 'T3', 'T4', 'T5', 'T6'], y=['Sáng', 'Chiều', 'Tối'], colorscale='Reds'))
        fig_heat.update_layout(title="🔥 Heatmap Tần suất Hoạt động", height=280, margin=dict(t=40, b=20, l=40, r=20), template="plotly_dark", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_heat, use_container_width=True)

    # --- TAB 3: POWER DASHBOARD ---
    with tab_dashboard:
        # Caching kết quả AI để chuyển Tab không bị mất tiền API
        if "ai_completed" not in st.session_state:
            with st.spinner("Đang tổng hợp dữ liệu thời gian thực và gọi API..."):
                st.session_state.p_rep = agent_planner(raw_data)
                st.session_state.f_rep = agent_finance(raw_data)
                st.session_state.r_rep = agent_risk_compliance(raw_data)
                st.session_state.b_rep = agent_banking_integration(raw_data)
                st.session_state.final_dec = agent_decision(f"{st.session_state.p_rep}\n\n[TÀI CHÍNH]\n{st.session_state.f_rep}\n\n[RỦI RO]\n{st.session_state.r_rep}")
                st.session_state.ai_completed = True

        layout_update = dict(template="plotly_dark", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", margin=dict(l=10, r=10, t=30, b=10), height=260)
        cash_col = df_cf.columns[-2]
        df_cf[cash_col] = pd.to_numeric(df_cf[cash_col].astype(str).str.replace(',', ''), errors='coerce')
        risk_col = df_txn.columns[-1]
        df_txn[risk_col] = pd.to_numeric(df_txn[risk_col], errors='coerce')
        df_txn['Nhãn'] = df_txn[risk_col].apply(lambda x: 'Nguy hiểm' if x >= 85 else 'An toàn')

        c1, c2, c3 = st.columns(3)
        with c1:
            fig_cf_line = px.line(df_cf, x=df_cf.columns[0], y=cash_col, title="📉 Xu hướng Dòng tiền", markers=True, color_discrete_sequence=['#3b82f6'])
            fig_cf_line.update_layout(**layout_update)
            st.plotly_chart(fig_cf_line, use_container_width=True, config={'displayModeBar': False})
        with c2:
            risk_counts = df_txn['Nhãn'].value_counts().reset_index()
            fig_pie = px.pie(risk_counts, values='count', names='Nhãn', title="🚨 Phân bổ Rủi ro", hole=0.6, color='Nhãn', color_discrete_map={'Nguy hiểm': '#ff4b4b', 'An toàn': '#00cc96'})
            fig_pie.update_layout(**layout_update, showlegend=False)
            st.plotly_chart(fig_pie, use_container_width=True, config={'displayModeBar': False})
        with c3:
            df_risk_top = df_txn.sort_values(by=risk_col, ascending=True).tail(5) 
            fig_bar = px.bar(df_risk_top, x=risk_col, y=df_txn.columns[0], orientation='h', title="🛡️ Top 5 Giao dịch Rủi ro", color=risk_col, color_continuous_scale='Reds')
            fig_bar.update_layout(**layout_update, showlegend=False)
            st.plotly_chart(fig_bar, use_container_width=True, config={'displayModeBar': False})

        st.markdown("<br>", unsafe_allow_html=True)
        c4, c5 = st.columns([2, 1])
        with c4:
            fig_scatter = px.scatter(df_txn, x=df_txn.columns[0], y=risk_col, color='Nhãn', size=risk_col, title="📍 Phân tán Rủi ro (Anomaly Detection)", color_discrete_map={'Nguy hiểm': '#ff4b4b', 'An toàn': '#00cc96'})
            fig_scatter.update_layout(**layout_update)
            st.plotly_chart(fig_scatter, use_container_width=True, config={'displayModeBar': False})
        with c5:
            avg_risk = df_txn[risk_col].mean()
            fig_gauge = go.Figure(go.Indicator(mode = "gauge+number", value = avg_risk, title = {'text': "🌡️ Áp lực Rủi ro"}, gauge = {'axis': {'range': [0, 100]}, 'bar': {'color': "#ff4b4b" if avg_risk > 60 else "#00cc96"}}))
            fig_gauge.update_layout(template="plotly_dark", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", margin=dict(l=20, r=20, t=50, b=20), height=260)
            st.plotly_chart(fig_gauge, use_container_width=True, config={'displayModeBar': False})

        st.markdown("### 🎯 Thẻ Quyết định (Decision Card)")
        st.error(st.session_state.final_dec)
        btn1, btn2 = st.columns(2)
        btn1.button("✅ DUYỆT (Approve)", use_container_width=True, type="primary")
        btn2.button("❌ TỪ CHỐI (Reject)", use_container_width=True)

    # --- TAB 4: CHAT & OFFICE ---
    with tab_chat:
        st.markdown("### 💬 Agent Command Line")
        agent_select = st.selectbox("Chọn Agent để tương tác:", ["Master Orchestrator", "Planner Agent", "Finance Agent", "Risk Agent"])
        chat_container = st.container(height=300)
        with chat_container:
            st.chat_message("assistant").write(f"Xin chào! Tôi là {agent_select}. Hệ thống đang lắng nghe...")
        prompt = st.chat_input(f"Giao task cho {agent_select}...")
        if prompt:
            with chat_container:
                st.chat_message("user").write(prompt)
                st.chat_message("assistant").write("Đang xử lý yêu cầu... (Tính năng chờ kết nối API)")

if __name__ == "__main__":
    main()
