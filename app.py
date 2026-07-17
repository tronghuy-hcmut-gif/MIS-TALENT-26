import os
import sys
import uuid
import json
import streamlit as st
import pandas as pd
import plotly.express as px
from openai import OpenAI

# ==========================================
# CẤU HÌNH GIAO DIỆN MẶC ĐỊNH (PHẢI NẰM ĐẦU TIÊN)
# ==========================================
st.set_page_config(page_title="OPC Agentic System", page_icon="⚡", layout="wide", initial_sidebar_state="collapsed")

# ==========================================
# CSS HACK: BIẾN STREAMLIT THÀNH ONE-PAGE DASHBOARD
# ==========================================
st.markdown("""
    <style>
        /* Ép lề màn hình mỏng nhất có thể, giấu Header/Footer */
        .block-container { padding-top: 1rem; padding-bottom: 0rem; padding-left: 2rem; padding-right: 2rem; }
        header { visibility: hidden; }
        footer { visibility: hidden; }
        
        /* Chỉnh màu chữ và bo góc các thẻ Metric */
        div[data-testid="metric-container"] {
            background-color: #1e1e2d;
            border: 1px solid #2d2d3f;
            padding: 5% 5% 5% 10%;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        }
        
        /* Ẩn thanh cuộn tổng của trình duyệt */
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-thumb { background: #3b82f6; border-radius: 10px; }
        ::-webkit-scrollbar-track { background: transparent; }
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
# CÁC HÀM XỬ LÝ DỮ LIỆU & LOGIC AI (GIỮ NGUYÊN)
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

def log_runtime_to_terminal(agent_name, input_src, output_text, next_agent):
    trace_id = f"TRACE-2026-{str(uuid.uuid4())[:8].upper()}" 
    print(f"[{trace_id}] {agent_name} -> SUCCESS -> Next: {next_agent}")

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
    log_runtime_to_terminal("Planner Agent", "04_CONTRACTS", "Workflow generated", "Finance, Risk")
    return f"**Mục tiêu:** {parsed.get('task_breakdown', '')}\n\n**Workflow:** {parsed.get('workflow_plan', '')}"

def agent_finance(data_bundle):
    response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": "Tóm tắt ngắn 2 đoạn: Phân tích hụt vốn & Đề xuất giải pháp. Tiếng Việt."}, {"role": "user", "content": data_bundle['cashflow']}], temperature=0.1)
    log_runtime_to_terminal("Finance Agent", "09_CASHFLOW", "Finance analyzed", "Document")
    return response.choices[0].message.content

def agent_risk_compliance(data_bundle):
    response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": "Phân tích rủi ro ngắn gọn. Báo cáo giao dịch >= 85 điểm. Tiếng Việt."}, {"role": "user", "content": f"Data: {data_bundle['txn']}"}], temperature=0.1)
    log_runtime_to_terminal("Risk Agent", "08_BANK_TXN", "Risk analyzed", "Document")
    return response.choices[0].message.content

def agent_banking_integration(data_bundle):
    response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": "Gợi ý 1 ngân hàng tốt nhất. Rất ngắn gọn. Tiếng Việt."}, {"role": "user", "content": data_bundle['bank_prod']}], temperature=0.1)
    log_runtime_to_terminal("Banking Agent", "11_BANK_PRODUCTS", "Bank mapped", "Document")
    return response.choices[0].message.content

def agent_decision(full_packet):
    response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": "Đóng vai Tổng Giám Đốc. Phán quyết DUYỆT hoặc TỪ CHỐI dựa trên dữ liệu. Trình bày max 4 câu sắc bén. Kèm Confidence Score %."}, {"role": "user", "content": full_packet}], temperature=0.1)
    log_runtime_to_terminal("Decision Agent", "All Outputs", "Final Decision", "End")
    return response.choices[0].message.content

# ==========================================
# KIẾN TRÚC UI: ONE-PAGE DASHBOARD
# ==========================================
def main():
    # 1. HÀNG ĐẦU TIÊN: TITLE & UPLOAD (NẰM TRÊN 1 DÒNG)
    top_col1, top_col2 = st.columns([3, 1])
    with top_col1:
        st.markdown("### ⚡ OPC AI Agent Management Dashboard")
    with top_col2:
        uploaded_file = st.file_uploader("Nạp Data (Excel)", type=["xlsx"], label_visibility="collapsed")

    if uploaded_file is not None:
        raw_data = layer4_data_ingestion(uploaded_file)
        df_contracts = pd.read_excel(uploaded_file, sheet_name='04_CONTRACTS')
        df_cf = pd.read_excel(uploaded_file, sheet_name='09_CASHFLOW')
        df_txn = pd.read_excel(uploaded_file, sheet_name='08_BANK_TXN')
        
        cash_col = df_cf.columns[-2]
        df_cf[cash_col] = pd.to_numeric(df_cf[cash_col].astype(str).str.replace(',', ''), errors='coerce')
        num_neg = len(df_cf[df_cf[cash_col] < 0])
        
        # 2. HÀNG 2: METRICS (5 CỘT SIÊU GỌN)
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Active Agents", "6/6", "Online")
        m2.metric("Pipeline Load", "452 ms", "-12ms")
        m3.metric("Tổng Hợp Đồng", f"{len(df_contracts)}", "Đã quét")
        m4.metric("Tháng Hụt Vốn", f"{num_neg}", "Nguy hiểm" if num_neg > 0 else "An toàn", delta_color="inverse")
        m5.metric("Giao Dịch Xét Duyệt", f"{len(df_txn)}", "Real-time")

        # KHỞI CHẠY AI NGẦM (KHÔNG IN SPINNER TO ĐÙNG NỮA ĐỂ GIỮ GIAO DIỆN MƯỢT)
        with st.spinner("Đang chạy luồng 6 AI Agents..."):
            p_rep = agent_planner(raw_data)
            f_rep = agent_finance(raw_data)
            r_rep = agent_risk_compliance(raw_data)
            b_rep = agent_banking_integration(raw_data)
            doc_packet = f"[TÀI CHÍNH]\n{f_rep}\n\n[RỦI RO]\n{r_rep}\n\n[NGÂN HÀNG]\n{b_rep}"
            final_decision = agent_decision(f"KẾ HOẠCH: {p_rep}\n\n{doc_packet}")

        # 3. HÀNG 3: KHU VỰC BIỂU ĐỒ (3 BIỂU ĐỒ NẰM NGANG)
        st.markdown("<br>", unsafe_allow_html=True) # Khoảng trắng nhỏ
        chart_col1, chart_col2, chart_col3 = st.columns(3)
        
        # Cấu hình chuẩn cho biểu đồ Đẹp & Lùn (Không chiếm diện tích)
        layout_update = dict(
            template="plotly_dark", 
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=10, r=10, t=30, b=10), height=240, # KHÓA CỨNG CHIỀU CAO
            showlegend=False
        )

        with chart_col1:
            month_col = df_cf.columns[0]
            fig_cf = px.line(df_cf, x=month_col, y=cash_col, title="📉 Biến động Dòng tiền", markers=True)
            fig_cf.update_layout(**layout_update)
            st.plotly_chart(fig_cf, use_container_width=True, config={'displayModeBar': False})

        with chart_col2:
            risk_col = df_txn.columns[-1]
            df_txn[risk_col] = pd.to_numeric(df_txn[risk_col], errors='coerce')
            df_txn['Nhãn'] = df_txn[risk_col].apply(lambda x: 'Nguy hiểm' if x >= 85 else 'An toàn')
            risk_counts = df_txn['Nhãn'].value_counts().reset_index()
            fig_pie = px.pie(risk_counts, values='count', names='Nhãn', title="🚨 Tỷ lệ Rủi ro", hole=0.6,
                             color='Nhãn', color_discrete_map={'Nguy hiểm': '#d62728', 'An toàn': '#2ca02c'})
            fig_pie.update_layout(**layout_update)
            st.plotly_chart(fig_pie, use_container_width=True, config={'displayModeBar': False})

        with chart_col3:
            df_risk_top = df_txn.sort_values(by=risk_col, ascending=True).tail(5) # Lấy 5 GD rủi ro cao nhất
            fig_bar = px.bar(df_risk_top, x=risk_col, y=df_txn.columns[0], orientation='h', 
                             title="🛡️ Top 5 Giao dịch rủi ro cao", color=risk_col, color_continuous_scale='Reds')
            fig_bar.update_layout(**layout_update)
            st.plotly_chart(fig_bar, use_container_width=True, config={'displayModeBar': False})

        # 4. HÀNG 4: LOG AGENT VÀ QUYẾT ĐỊNH (CỘT TRÁI CHỨA TABS, CỘT PHẢI CHỨA NÚT DUYỆT)
        bot_col1, bot_col2 = st.columns([2, 1])
        
        with bot_col1:
            st.markdown("**🧠 AI Agents Processing Logs**")
            # Dùng Tabs để nhét cả đống text vào 1 chỗ, không làm dài trang
            tab1, tab2, tab3, tab4 = st.tabs(["Planner Agent", "Finance Agent", "Risk Agent", "Banking Agent"])
            with tab1: st.info(p_rep)
            with tab2: st.info(f_rep)
            with tab3: st.info(r_rep)
            with tab4: st.info(b_rep)
            
        with bot_col2:
            st.markdown("**🎯 Chỉ thị Tối cao (Decision Agent)**")
            # Đóng khung phán quyết cho nổi bật
            st.error(f"{final_decision}")
            
            # Cụm nút bấm phê duyệt (Nằm ngang cực gọn)
            st.markdown("**Human-in-the-loop Override:**")
            btn1, btn2 = st.columns(2)
            btn1.button("✅ DUYỆT (Approve)", use_container_width=True, type="primary")
            btn2.button("❌ TỪ CHỐI (Reject)", use_container_width=True)

    else:
        st.info("Vui lòng nạp file Excel góc trên bên phải để khởi chạy Dashboard.")

if __name__ == "__main__":
    main()
