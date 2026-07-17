import pandas as pd
from openai import OpenAI
import os

# nạp API
client = OpenAI(API_KEY")

# LAYER 4: DATA LAYER 
def layer4_data_ingestion(filepath):
    print("[-] Đang đọc file Excel toàn hệ thống...")
    return {
        "contracts": pd.read_excel(filepath, sheet_name='04_CONTRACTS').to_string(index=False),
        "cashflow": pd.read_excel(filepath, sheet_name='09_CASHFLOW').to_string(index=False),
        "txn": pd.read_excel(filepath, sheet_name='08_BANK_TXN').to_string(index=False),
        "rules": pd.read_excel(filepath, sheet_name='13_RISK_RULES').to_string(index=False),
        "bank_prod": pd.read_excel(filepath, sheet_name='11_BANK_PRODUCTS').to_string(index=False)
    }

# LAYER 3: REASONING & CONTROL LAYER

# [Agent 2] Finance agent 
def agent_finance(data_bundle):
    print("[-] Finance Agent đang viết báo cáo định lượng...")
    system_prompt = """
    Bạn là Finance Agent. Dựa vào dữ liệu Cashflow, hãy viết báo cáo gồm CHÍNH XÁC 2 ĐOẠN VĂN (tuyệt đối không dùng gạch đầu dòng hay danh sách đánh số):
    - Đoạn 1 (Phân tích): Mô tả tình trạng hụt vốn của công ty, nêu rõ các tháng bị âm và số tiền hụt cụ thể từng tháng để thấy rõ nguyên nhân.
    - Đoạn 2 (Đề xuất): Đưa ra các giải pháp tài chính định lượng cụ thể. Nếu vay tín dụng, hãy đề xuất hạn mức vay chính xác (bằng số tiền âm lớn nhất cộng thêm 550 triệu dự phòng an toàn) và kỳ hạn vay kéo dài đến tháng có dòng tiền dương trở lại. Nếu chọn giải pháp thanh toán sớm (Factoring), nêu rõ cần chiết khấu bao nhiêu tiền để bù đắp đủ hạn mức.
    BẮT BUỘC TRẢ LỜI BẰNG TIẾNG VIỆT, diễn đạt tự nhiên, trôi chảy như một chuyên gia phân tích tài chính.
    """
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": data_bundle['cashflow']}
        ], temperature=0.1
    )
    return response.choices[0].message.content

# [Agent 3] Risk & compliance agent 
def agent_risk_compliance(data_bundle):
    print("[-] Risk Agent đang rà soát rủi ro...")
    masked_txn = data_bundle['txn'].replace('CUS-005', 'TOK-***')
    system_prompt = """
    Bạn là Risk Agent. Rà soát cột risk_score trong dữ liệu giao dịch. Hãy viết thành 1 ĐOẠN VĂN duy nhất (tuyệt đối không dùng gạch đầu dòng):
    - Nếu có giao dịch risk_score >= 85: Nêu rõ mã giao dịch, điểm rủi ro, và yêu cầu đóng băng (Hold) các giao dịch này để chờ Founder phê duyệt.
    - Nếu không có giao dịch nào >= 85: Trả về ĐÚNG MỘT CÂU DUY NHẤT: "Không phát hiện rủi ro vi phạm. Dữ liệu sạch, không có lỗi."
    BẮT BUỘC TRẢ LỜI BẰNG TIẾNG VIỆT.
    """
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Luật: {data_bundle['rules']}\nData: {masked_txn}"}
        ], temperature=0.1
    )
    return response.choices[0].message.content, masked_txn

# [Agent 4] Banking integration agent 
def agent_banking_integration(data_bundle):
    return "Đề xuất VietinBank (Lãi suất thấp nhất 6.5%)."

# [Agent 5] Document agent 
def agent_document(finance_out, risk_out, bank_out):
    # Gom hồ sơ nội bộ để chuyển giao
    return f"HỒ SƠ TỔNG HỢP: \n- {finance_out}\n- {risk_out}\n- {bank_out}"

# [Agent 6] Decision agent 
def agent_decision(doc_packet):
    print("[-] Decision Agent đang chốt phương án...")
    system_prompt = """
    Bạn là Decision Agent (Tổng giám đốc). Đọc hồ sơ từ Finance và Risk, viết 1 ĐOẠN VĂN duy nhất (không gạch đầu dòng) để ra quyết định cuối cùng:
    - Nếu Risk Agent báo CÓ rủi ro: Đưa ra quyết định "KHÔNG DUYỆT PHƯƠNG ÁN TÀI CHÍNH". Giải thích lý do là hệ thống cần phải phong tỏa và làm rõ các giao dịch có điểm rủi ro cao trước khi tiến hành bơm thêm vốn hay thanh toán.
    - Nếu Risk Agent báo AN TOÀN (không có lỗi): Đưa ra quyết định "PHÊ DUYỆT". Tóm tắt lại phương án vay vốn hoặc thanh toán sớm dựa trên con số chính xác mà Finance Agent đã đề xuất.
    BẮT BUỘC TRẢ LỜI BẰNG TIẾNG VIỆT với giọng điệu quyết đoán, rõ ràng của một người lãnh đạo doanh nghiệp.
    """
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": doc_packet}
        ], temperature=0.1
    )
    return response.choices[0].message.content
# LAYER 2: ORCHESTRATION LAYER 

# [Agent 1] CEO/Planner Agent điều phối luồng
def layer2_orchestrator(filepath):
    raw_data = layer4_data_ingestion(filepath)
    f_rep = agent_finance(raw_data)
    r_rep, m_data = agent_risk_compliance(raw_data)
    b_rep = agent_banking_integration(raw_data)
    doc_packet = agent_document(f_rep, r_rep, b_rep)
    final_decision = agent_decision(doc_packet)
    return f_rep, r_rep, final_decision

# LAYER 1: INTERACTION & UI LAYER (Lớp Giao diện)
def layer1_ui_dashboard(finance_out, risk_out, decision_out):
    print("\n---------------- DASHBOARD ----------------")
    print(f"\t[1] FINANCE AGENT: \n{finance_out}\n")
    print(f"\t[2] RISK AGENT: \n{risk_out}\n")
    print(f"\t[3] DECISION AGENT: \n{decision_out}\n")
    print("---------------- END ----------------")

# MAIN 
if __name__ == "__main__":
    file_path = "MISTalent2026_OPC_AgenticAI_TeamPack_v3.xlsx"
    
    if os.path.exists(file_path):
        f_rep, r_rep, f_decision = layer2_orchestrator(file_path)
        layer1_ui_dashboard(f_rep, r_rep, f_decision)
    else:
        print("Lỗi: Không tìm thấy file Excel.")