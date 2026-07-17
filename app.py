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

st.markdown("""
    <style>
        .block-container { padding-top: 1.5rem; padding-bottom: 1rem; }
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-thumb { background: #ff4b4b; border-radius: 10px; }
        ::-webkit-scrollbar-track { background: transparent; }
        .stTabs [data-baseweb="tab-list"] { gap: 8px; border-bottom: 1px solid #2d2d3f; }
        .stTabs [data-baseweb="tab"] { padding: 10px 20px; background-color: #1e1e2d; border-radius: 5px 5px 0 0; }
        .stTabs [aria-selected="true"] { background-color: #ff4b4b !important; color: white !important; }
        div[data-testid="metric-container"] { background-color: #1e1e2d; border: 1px solid #2d2d3f; padding: 5%; border-radius: 8px; }
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
    col1, col2 = st.columns([4, 1])
    with col1:
        st.markdown("## ⚡ OPC Multi-Agent Command Center")
    with col2:
        uploaded_file = st.file_uploader("Nạp Data (Excel)", type=["xlsx"], label_visibility="collapsed")

    if uploaded_file is None:
        st.info("👈 Vui lòng tải file dữ liệu lên để kích hoạt hệ thống phân tích tín dụng tự động.")
        return

    # Load data
    raw_data = layer4_data_ingestion(uploaded_file)
    df_cf = pd.read_excel(uploaded_file, sheet_name='09_CASHFLOW')
    df_txn = pd.read_excel(uploaded_file, sheet_name='08_BANK_TXN')

    # Khởi tạo 4 Tabs chính
    tab_overview, tab_agents, tab_dashboard, tab_chat = st.tabs([
        "🌐 Overview", "🤖 Agents Fleet", "📊 Power Dashboard", "💬 Office & Chat"
    ])

    # ---------------------------------------------------------
    # TAB 1: OVERVIEW (Tổng quan hệ thống)
    # ---------------------------------------------------------
    with tab_overview:
        st.markdown("### 📡 Trung tâm Điều hành AI (System Overview)")
        st.caption("Tổng quan kiến trúc mô hình và các thông số vận hành cốt lõi của hệ thống đa tác nhân (Multi-Agent System). Báo cáo trạng thái On/Off của các cụm xử lý độc lập[cite: 1].")
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("LLM Engine", "gpt-4o", "Core API Online")
        m2.metric("Lực lượng Agent", "6 Chuyên gia", "Đang trực chiến")
        m3.metric("Tiến trình Task", "85% Hoàn thành", "Tốc độ xử lý +12%")
        m4.metric("Tài nguyên Token", "1,245,000", "Trong mức an toàn")
        
        st.divider()
        col_act, col_arch = st.columns([1, 1])
        
        with col_act:
            st.markdown("**🔄 Chuỗi nhiệm vụ thời gian thực (Recent Activities)**")
            st.caption("Theo dõi tiến độ hoàn thành các tác vụ thành phần của các Agent trong chu kỳ hiện tại[cite: 1].")
            st.progress(100, text="Planner Agent: Đã khởi tạo cấu trúc Workflow (100%)")
            st.progress(100, text="Data Agent: Đã bóc tách dữ liệu từ Excel (100%)")
            st.progress(80, text="Risk Agent: Đang quét dị thường giao dịch (80%)")
            st.progress(45, text="Finance Agent: Đang dự phóng hụt vốn dòng tiền (45%)")
            
        with col_arch:
            st.markdown("**🧠 Kiến trúc Suy luận (Reasoning Framework)**")
            st.info("""
            **Luồng xử lý dữ liệu chuẩn:**
            1. **Dữ liệu đầu vào (Input):** Nạp và làm sạch dữ liệu thô từ Excel (Hợp đồng, Dòng tiền, Giao dịch).
            2. **Điều phối viên (Orchestrator):** Tiếp nhận tín hiệu và phân rã các tập dữ liệu.
            3. **Tầng suy luận (Agentic Layer):** 6 Agent chuyên trách độc lập phân tích dữ liệu chuyên sâu thông qua API.
            4. **Kết xuất (Output):** Khuyến nghị quyết định, tính toán độ tin cậy (Confidence Score) và báo cáo tổng hợp.
            """)

    # ---------------------------------------------------------
    # TAB 2: AGENT FLEET (Theo dõi từng Agent)
    # ---------------------------------------------------------
    with tab_agents:
        st.markdown("### 🤖 Báo cáo Năng lực Lực lượng (Agents Fleet Status)")
        st.caption("Đo lường chi tiết khối lượng công việc, hiệu suất và nhật ký hoạt động của từng đặc vụ AI[cite: 1].")
        
        a1, a2, a3 = st.columns(3)
        with a1:
            st.success("**🎯 Planner Agent** (Trạng thái: Hoạt động)\n\n- **Nhiệm vụ:** Hoạch định chiến lược và thiết lập Workflow.\n- **Đã xử lý:** 420 tasks\n- **Mức độ đóng góp:** 25% tổng tiến trình.")
        with a2:
            st.warning("**🛡️ Risk Agent** (Trạng thái: Đang phân tích)\n\n- **Nhiệm vụ:** Rà soát tuân thủ và chấm điểm rủi ro.\n- **Đã xử lý:** 315 tasks\n- **Mức độ đóng góp:** 30% tổng tiến trình.")
        with a3:
            st.info("**📊 Finance Agent** (Trạng thái: Chờ lệnh)\n\n- **Nhiệm vụ:** Phân tích dòng tiền và dự phóng lợi nhuận.\n- **Đã xử lý:** 150 tasks\n- **Mức độ đóng góp:** 15% tổng tiến trình.")
            
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("**🔥 Heatmap Tần suất Hoạt động (Workload Distribution)**")
        st.caption("Biểu đồ nhiệt phân bổ tài nguyên. Vùng màu đậm thể hiện thời gian cao điểm (Peak Hours) khi hệ thống phải xử lý lượng Task khổng lồ, giúp tối ưu hóa việc phân luồng dữ liệu.")
        
        # Heatmap
        z = [[1, 20, 30, 50, 1], [20, 1, 60, 80, 30], [30, 60, 1, -10, 20]]
        fig_heat = go.Figure(data=go.Heatmap(
            z=z, 
            x=['T2', 'T3', 'T4', 'T5', 'T6'], 
            y=['Sáng', 'Chiều', 'Tối'],
            colorscale='Reds'
        ))
        fig_heat.update_layout(height=280, margin=dict(t=20, b=20, l=40, r=20), template="plotly_dark", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_heat, use_container_width=True)

    # ---------------------------------------------------------
    # TAB 3: POWER DASHBOARD (NGẬP TRÀN BIỂU ĐỒ)
    # ---------------------------------------------------------
    with tab_dashboard:
        with st.spinner("Đang tổng hợp dữ liệu thời gian thực..."):
            p_rep = agent_planner(raw_data)
            f_rep = agent_finance(raw_data)
            r_rep = agent_risk_compliance(raw_data)
            b_rep = agent_banking_integration(raw_data)
            final_decision = agent_decision(f"{p_rep}\n\n[TÀI CHÍNH]\n{f_rep}\n\n[RỦI RO]\n{r_rep}")

        layout_update = dict(template="plotly_dark", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", margin=dict(l=10, r=10, t=30, b=10), height=260)
        
        # Tiền xử lý Data cho biểu đồ
        cash_col = df_cf.columns[-2]
        df_cf[cash_col] = pd.to_numeric(df_cf[cash_col].astype(str).str.replace(',', ''), errors='coerce')
        risk_col = df_txn.columns[-1]
        df_txn[risk_col] = pd.to_numeric(df_txn[risk_col], errors='coerce')
        df_txn['Nhãn'] = df_txn[risk_col].apply(lambda x: 'Nguy hiểm' if x >= 85 else 'An toàn')

        # --- HÀNG BIỂU ĐỒ SỐ 1 (3 CỘT) ---
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

        # --- HÀNG BIỂU ĐỒ SỐ 2 (2 CỘT) ---
        st.markdown("<br>", unsafe_allow_html=True)
        c4, c5 = st.columns([2, 1])

        with c4:
            fig_scatter = px.scatter(df_txn, x=df_txn.columns[0], y=risk_col, color='Nhãn', size=risk_col, title="📍 Phân tán Rủi ro (Anomaly Detection)", color_discrete_map={'Nguy hiểm': '#ff4b4b', 'An toàn': '#00cc96'})
            fig_scatter.update_layout(**layout_update)
            st.plotly_chart(fig_scatter, use_container_width=True, config={'displayModeBar': False})
            
        with c5:
            avg_risk = df_txn[risk_col].mean()
            fig_gauge = go.Figure(go.Indicator(
                mode = "gauge+number", value = avg_risk, title = {'text': "🌡️ Áp lực Rủi ro Toàn cục"},
                gauge = {'axis': {'range': [0, 100]}, 'bar': {'color': "#ff4b4b" if avg_risk > 60 else "#00cc96"}}
            ))
            fig_gauge.update_layout(template="plotly_dark", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", margin=dict(l=20, r=20, t=50, b=20), height=260)
            st.plotly_chart(fig_gauge, use_container_width=True, config={'displayModeBar': False})

        # --- THẺ QUYẾT ĐỊNH CỦA TỔNG GIÁM ĐỐC ---
        st.markdown("### 🎯 Thẻ Quyết định (Decision Card)")
        st.error(final_decision)
        btn1, btn2 = st.columns(2)
        btn1.button("✅ DUYỆT (Approve)", use_container_width=True, type="primary")
        btn2.button("❌ TỪ CHỐI (Reject)", use_container_width=True)

    # ---------------------------------------------------------
    # TAB 4: CHAT & OFFICE
    # ---------------------------------------------------------
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
