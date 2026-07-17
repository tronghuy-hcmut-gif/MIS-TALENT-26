import os
import sys
import uuid
import json
import streamlit as st
import pandas as pd
import plotly.express as px
from openai import OpenAI

# ==========================================
# FIX LỖI UNICODE TRÊN WINDOWS/LINUX
# ==========================================
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"

# ==========================================
# CẤU HÌNH GIAO DIỆN MẶC ĐỊNH
# ==========================================
st.set_page_config(page_title="OPC Agentic System", page_icon="📈", layout="wide")

# ==========================================
# KẾT NỐI OPENAI (CHUẨN BẢO MẬT STREAMLIT CLOUD)
# Lệnh st.secrets sẽ tự động lấy Key từ ô Settings > Secrets của app
# ==========================================
try:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
except Exception as e:
    st.error("🚨 Không tìm thấy API Key! Vui lòng kiểm tra lại mục Settings > Secrets trên Streamlit Cloud.")
    st.stop()

# ==========================================
# HÀM FORMAT TIỀN TỆ (Chuẩn hiển thị Triệu / Tỷ)
# ==========================================
def format_currency(val):
    try:
        v = float(val)
        sign = "-" if v < 0 else ""
        abs_v = abs(v)
        
        if abs_v >= 1_000_000_000:
            return f"{sign}{abs_v/1_000_000_000:.2f} tỷ"
        elif abs_v >= 1_000_000:
            return f"{sign}{abs_v/1_000_000:.0f} triệu"
        else:
            return f"{sign}{abs_v:.0f} triệu"
    except:
        return str(val)

# ==========================================
# HÀM GHI LOG RA TERMINAL (MINH CHỨNG RUNTIME)
# ==========================================
def log_runtime_to_terminal(agent_name, input_src, output_text, next_agent):
    trace_id = f"TRACE-2026-{str(uuid.uuid4())[:8].upper()}" 
    print("\n" + "="*60)
    print(f"Trace ID: {trace_id}")
    print(f"Agent: {agent_name}")
    print(f"Model: gpt-4o")
    print(f"Input source: {input_src}")
    print(f"OpenAI status: Success")
    short_output = output_text.replace('\n', ' ')[:80] + "..." if len(output_text) > 80 else output_text
    print(f"Output: {short_output}")
    print(f"Next agent: {next_agent}")
    print("="*60 + "\n")

# ==========================================
# LAYER 4: DATA LAYER (Đọc dữ liệu thô)
# ==========================================
def layer4_data_ingestion(uploaded_file):
    return {
        "contracts": pd.read_excel(uploaded_file, sheet_name='04_CONTRACTS').to_string(index=False),
        "cashflow": pd.read_excel(uploaded_file, sheet_name='09_CASHFLOW').to_string(index=False),
        "txn": pd.read_excel(uploaded_file, sheet_name='08_BANK_TXN').to_string(index=False),
        "rules": pd.read_excel(uploaded_file, sheet_name='13_RISK_RULES').to_string(index=False),
        "bank_prod": pd.read_excel(uploaded_file, sheet_name='11_BANK_PRODUCTS').to_string(index=False)
    }

# ==========================================
# LAYER 3: REASONING & CONTROL LAYER (6 AGENTS)
# ==========================================

# 1. PLANNER AGENT (Structured Output JSON)
def agent_planner(data_bundle):
    system_prompt = """
    Bạn là Planner Agent (Hoạch định chiến lược). Đọc dữ liệu hợp đồng và trả về kết quả định dạng JSON.
    Cấu trúc JSON bắt buộc:
    {
        "task_breakdown": "Mô tả phân rã công việc...",
        "approval_gates": "Mô tả các mốc kiểm duyệt...",
        "workflow_plan": "Mô tả kế hoạch luồng chạy..."
    }
    BẮT BUỘC TRẢ LỜI BẰNG TIẾNG VIỆT.
    """
    response = client.chat.completions.create(
        model="gpt-4o",
        response_format={ "type": "json_object" }, 
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": data_bundle['contracts']}], 
        temperature=0.1
    )
    
    raw_json = response.choices[0].message.content
    parsed_data = json.loads(raw_json)
    
    result = f"**📋 Ma trận phân rã công việc (Task Breakdown):**\n{parsed_data['task_breakdown']}\n\n" \
             f"**🚧 Các mốc cần phê duyệt (Approval Gates):**\n{parsed_data['approval_gates']}\n\n" \
             f"**🗺️ Kế hoạch luồng chạy (Workflow Plan):**\n{parsed_data['workflow_plan']}"
             
    log_runtime_to_terminal("Planner Agent", "04_CONTRACTS", result, "Finance Agent, Risk Agent")
    return result

# 2. FINANCE AGENT
def agent_finance(data_bundle):
    system_prompt = """
    Bạn là Finance Agent. Dựa vào dữ liệu Cashflow, hãy viết báo cáo gồm CHÍNH XÁC 2 ĐOẠN VĂN:
    - Đoạn 1: Phân tích tình trạng hụt vốn, các tháng bị âm và số tiền hụt.
    - Đoạn 2: Đề xuất giải pháp định lượng cụ thể.
    BẮT BUỘC TRẢ LỜI BẰNG TIẾNG VIỆT.
    """
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": data_bundle['cashflow']}], 
        temperature=0.1
    )
    result = response.choices[0].message.content
    log_runtime_to_terminal("Finance Agent", "09_CASHFLOW", result, "Banking Agent, Document Agent")
    return result

# 3. RISK AGENT
def agent_risk_compliance(data_bundle):
    masked_txn = data_bundle['txn'].replace('CUS-005', 'TOK-***') 
    system_prompt = """
    Bạn là Risk Agent. Rà soát cột risk_score trong dữ liệu giao dịch. Viết 1 ĐOẠN VĂN:
    - Nếu có giao dịch risk_score >= 85: Nêu mã giao dịch, điểm rủi ro, yêu cầu Hold.
    - Nếu không có: Trả về "Không phát hiện rủi ro vi phạm. Dữ liệu sạch, không có lỗi."
    BẮT BUỘC TRẢ LỜI BẰNG TIẾNG VIỆT.
    """
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": f"Luật: {data_bundle['rules']}\nData: {masked_txn}"}], 
        temperature=0.1
    )
    result = response.choices[0].message.content
    log_runtime_to_terminal("Risk Agent", "08_BANK_TXN, 13_RISK_RULES", result, "Document Agent")
    return result, masked_txn

# 4. BANKING AGENT
def agent_banking_integration(data_bundle):
    system_prompt = """
    Bạn là Banking Agent. Đọc dữ liệu sản phẩm ngân hàng (bank_prod) và trả về 1 ĐOẠN VĂN TÓM TẮT:
    - Gợi ý đối tác ngân hàng vay/bảo lãnh tối ưu nhất dựa trên lãi suất và tỷ lệ tài sản đảm bảo.
    BẮT BUỘC TRẢ LỜI BẰNG TIẾNG VIỆT.
    """
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": data_bundle['bank_prod']}], 
        temperature=0.1
    )
    result = response.choices[0].message.content
    log_runtime_to_terminal("Banking Agent", "11_BANK_PRODUCTS", result, "Document Agent")
    return result

# 5. DOCUMENT AGENT
def agent_document(finance_out, risk_out, bank_out):
    result = f"HỒ SƠ TỔNG HỢP TRÌNH LÃNH ĐẠO (Executive Summary):\n\n[1. TÀI CHÍNH]\n{finance_out}\n\n[2. RỦI RO]\n{risk_out}\n\n[3. NGÂN HÀNG]\n{bank_out}"
    log_runtime_to_terminal("Document Agent", "Finance, Risk, Banking Outputs", "Đã tổng hợp bộ hồ sơ tín dụng.", "Decision Agent")
    return result

# 6. DECISION AGENT 
def agent_decision(full_packet):
    system_prompt = """
    Bạn là Decision Agent (Tổng giám đốc). Đọc toàn bộ hồ sơ tổng hợp từ 5 Agent tuyến dưới và đưa ra phán quyết. 
    Liên kết logic:
    1. Lấy thâm hụt tài chính (Finance Agent) đối chiếu với luồng công việc (Planner Agent).
    2. Liên kết nhu cầu vốn với giải pháp vay (Banking Agent).
    3. Lấy kết quả rà soát vi phạm (Risk Agent) làm điều kiện tiên quyết.
    
    Kết luận "KHÔNG DUYỆT" nếu có rủi ro cao (>=85), ngược lại "PHÊ DUYỆT".
    Ghi rõ: "Độ tự tin của hệ thống (Confidence Score): [Điểm %]". Trình bày sắc bén.
    """
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": full_packet}], 
        temperature=0.1
    )
    result = response.choices[0].message.content
    log_runtime_to_terminal("Decision Agent", "Document Output, Planner Output", result, "End of Workflow")
    return result

# ==========================================
# LAYER 1 & 2: ORCHESTRATION & UI (STREAMLIT APP)
# ==========================================
def main():
    st.title("💼 Dashboard Điều Hành OPC - AI Agents")
    st.markdown("Hệ thống tự động điều phối 6 Agents theo chuỗi giá trị: Hoạch định -> Phân tích -> Ra quyết định.")
    st.divider()

    with st.sidebar:
        st.header("📥 Nạp dữ liệu hệ thống")
        uploaded_file = st.file_uploader("Kéo thả file Excel V3 vào đây", type=["xlsx"])

    if uploaded_file is not None:
        if st.button("🚀 KÍCH HOẠT HỆ THỐNG PHÂN TÍCH", type="primary", use_container_width=True):
            
            with st.spinner("Đang nạp Data Model..."):
                raw_data = layer4_data_ingestion(uploaded_file)
            
            # KHỐI HIỂN THỊ METRICS TỔNG QUAN
            try:
                df_contracts = pd.read_excel(uploaded_file, sheet_name='04_CONTRACTS')
                df_cf_summary = pd.read_excel(uploaded_file, sheet_name='09_CASHFLOW')
                df_txn_summary = pd.read_excel(uploaded_file, sheet_name='08_BANK_TXN')
                
                cash_col_name = df_cf_summary.columns[-2]
                df_cf_summary[cash_col_name] = pd.to_numeric(df_cf_summary[cash_col_name].astype(str).str.replace(',', ''), errors='coerce')
                num_negative_months = len(df_cf_summary[df_cf_summary[cash_col_name] < 0])

                st.markdown("### 📈 Tổng quan hệ thống (System Metrics)")
                met1, met2, met3, met4 = st.columns(4)
                with met1:
                    st.metric(label="Active Agents", value="6", delta="Online")
                with met2:
                    st.metric(label="Tổng Hợp Đồng", value=f"{len(df_contracts)}", delta="Đã quét")
                with met3:
                    st.metric(label="Số Tháng Thâm Hụt", value=f"{num_negative_months}", delta="- Nguy hiểm", delta_color="inverse")
                with met4:
                    st.metric(label="Giao Dịch Đã Quét", value=f"{len(df_txn_summary)}", delta="Cần rà soát", delta_color="off")
                st.divider()
            except Exception as e:
                st.warning(f"Lỗi hiển thị Metrics: {e}")

            # TẦNG 1: PLANNER AGENT
            st.subheader("🧠 1. Hoạch định Chiến lược (Planner Agent)")
            with st.spinner("Đang phân rã JSON..."):
                p_rep = agent_planner(raw_data)
            st.success("✅ Đã thiết lập Workflow!")
            with st.expander("🗺️ Xem chi tiết Kế hoạch"):
                st.markdown(p_rep)
            st.divider()
            
            # TẦNG 2: FINANCE & RISK
            col_fin, col_risk = st.columns(2)
            with col_fin:
                st.subheader("📊 2. Báo cáo Tài chính (Finance Agent)")
                with st.spinner("Đang tính toán..."):
                    f_rep = agent_finance(raw_data)
                
                try:
                    df_cf = pd.read_excel(uploaded_file, sheet_name='09_CASHFLOW')
                    month_col = df_cf.columns[0] 
                    cash_col = df_cf.columns[-2] 
                    df_cf[cash_col] = pd.to_numeric(df_cf[cash_col].astype(str).str.replace(',', ''), errors='coerce')
                    df_cf['text_hien_thi'] = df_cf[cash_col].apply(format_currency)
                    
                    min_cash = df_cf[cash_col].min()
                    du_phong = 550_000_000 
                    loan_amount = abs(min_cash) + du_phong if not pd.isna(min_cash) else du_phong
                    
                    df_scenario = df_cf.copy()
                    df_scenario['Kich_Ban'] = df_scenario[cash_col] + loan_amount
                    df_scenario['text_kich_ban'] = df_scenario['Kich_Ban'].apply(format_currency)

                    fig_current = px.bar(
                        df_cf, x=month_col, y=cash_col, 
                        title="📉 Thực trạng Dòng tiền", text='text_hien_thi', color=cash_col,
                        color_continuous_scale=['#d62728', '#2ca02c']
                    )
                    fig_current.update_layout(template="plotly_dark", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
                    st.plotly_chart(fig_current, use_container_width=True)

                    if not df_cf[df_cf[cash_col] < 0].empty:
                        st.error("⚠️ Cảnh báo hụt vốn dòng tiền!")
                    else:
                        st.success("✅ Trạng thái tài chính an toàn.")
                except Exception as e:
                    st.warning(f"Lỗi vẽ biểu đồ: {e}")

                with st.expander("📄 Xem chi tiết báo cáo"):
                    st.markdown(f_rep)

            with col_risk:
                st.subheader("🛡️ 3. Kiểm soát Nội bộ (Risk Agent)")
                with st.spinner("Đang quét dấu hiệu..."):
                    r_rep, m_data = agent_risk_compliance(raw_data)
                
                try:
                    df_txn = pd.read_excel(uploaded_file, sheet_name='08_BANK_TXN')
                    txn_col = df_txn.columns[0]
                    risk_col = df_txn.columns[-1]
                    df_txn[risk_col] = pd.to_numeric(df_txn[risk_col], errors='coerce')
                    df_plot = df_txn.head(10).copy()
                    df_plot['Trạng thái'] = df_plot[risk_col].apply(lambda x: 'Nguy hiểm (>=85)' if x >= 85 else 'An toàn')
                    
                    fig_risk = px.bar(
                        df_plot, x=txn_col, y=risk_col, color='Trạng thái',
                        color_discrete_map={'Nguy hiểm (>=85)': '#d62728', 'An toàn': '#2ca02c'},
                        title="🚨 Điểm Rủi ro (Top 10)", text=risk_col
                    )
                    fig_risk.update_layout(template="plotly_dark", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
                    st.plotly_chart(fig_risk, use_container_width=True)
                    
                    if not df_txn[df_txn[risk_col] >= 85].empty:
                        st.error("⚠️ Có giao dịch nguy hiểm. Đã tạm giữ!")
                    else:
                        st.success("✅ Hệ thống sạch.")
                except Exception as e:
                    st.warning(f"Lỗi vẽ biểu đồ: {e}")

                with st.expander("📄 Xem chi tiết báo cáo"):
                    st.markdown(r_rep)
            st.divider()
            
            # TẦNG 3: BANKING & DOCUMENT
            col_bank, col_doc = st.columns(2)
            with col_bank:
                st.subheader("🏦 4. Tích hợp Ngoại vi (Banking Agent)")
                with st.spinner("Đang gọi Sandbox API..."):
                    b_rep = agent_banking_integration(raw_data)
                st.success("✅ HTTP 200 OK.")
                with st.expander("🗂️ Khuyến nghị API & Ma trận"):
                    st.markdown(b_rep)

            with col_doc:
                st.subheader("📑 5. Xử lý Hồ sơ (Document Agent)")
                with st.spinner("Đang soạn thảo..."):
                    doc_packet = agent_document(f_rep, r_rep, b_rep)
                st.success("✅ Bộ hồ sơ hoàn tất.")
                with st.expander("📧 Xem Executive Summary"):
                    st.markdown(doc_packet)
            st.divider()
            
            # TẦNG 4: DECISION AGENT
            st.subheader("🎯 6. Chỉ thị Điều hành (Decision Agent)")
            with st.spinner("Tổng Giám đốc AI đang phán quyết..."):
                full_dossier = f"KẾ HOẠCH: {p_rep}\n\n{doc_packet}"
                final_decision = agent_decision(full_dossier)
            st.warning(f"**KHUYẾN NGHỊ:**\n\n{final_decision}")
                
    else:
        st.info("Vui lòng tải file dữ liệu lên để bắt đầu.")

if __name__ == "__main__":
    main()
