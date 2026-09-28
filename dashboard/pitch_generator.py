"""
Facebook Lead Intelligence V1 - AI Sales Pitch & Outreach Script Generator

Generates high-converting, personalized outreach messages tailored to each lead's
detected product, quantity, intent, and contact details.
"""

from typing import Dict, Any

def generate_sales_pitch(lead: Dict[str, Any]) -> Dict[str, str]:
    name = lead.get("full_name") or "Quý Khách Hàng"
    product = lead.get("product_interest") or "Thiết bị & Vật tư xây dựng"
    intent = lead.get("primary_intent") or "REQUEST_QUOTE"
    company = lead.get("company_name")
    phone = lead.get("primary_phone") or ""
    score = lead.get("lead_score") or 0

    greeting = f"Em chào anh/chị {name}"
    if company and company != "-":
        greeting += f" bên {company}"
    greeting += ","

    # Tone tailored to intent
    if intent == "REQUEST_QUOTE":
        intro = f"Em thấy mình đang quan tâm và cần bảng báo giá chi tiết về **{product}** phục vụ thi công công trình."
        value_prop = (
            f"Hiện tại bên em đang có chính sách giá trực tiếp từ nhà máy/tổng kho đối với dòng {product}, "
            f"hỗ trợ đầy đủ CO/CQ, hóa đơn VAT và vận chuyển tận chân công trình."
        )
        cta = (
            f"Em xin phép gửi bảng báo giá chi tiết kèm chiết khấu tốt nhất qua Zalo số này nhé ạ. "
            f"Hoặc anh/chị cho em xin ít phút gọi điện để tư vấn quy cách phù hợp nhất!"
        )
    elif intent == "LOOKING_TO_BUY":
        intro = f"Em thấy anh/chị đang có nhu cầu tìm mua **{product}** gấp cho dự án."
        value_prop = (
            f"Dòng {product} bên em hiện đang sẵn hàng số lượng lớn tại kho, cam kết tiến độ giao hàng ngay trong 24h, "
            f"bảo hành chính hãng và hỗ trợ kỹ thuật tận nơi."
        )
        cta = (
            f"Anh/chị cho em xin quy cách hoặc khối lượng dự kiến để em báo giá và giữ hàng sớm nhất cho mình nhé ạ!"
        )
    else:
        intro = f"Em liên hệ từ bộ phận giải pháp xây dựng, thấy mình đang tìm hiểu về **{product}**."
        value_prop = (
            f"Bên em là đơn vị chuyên cung cấp {product} và giải pháp thi công toàn diện cho các nhà thầu tại Việt Nam."
        )
        cta = f"Em gửi anh/chị tài liệu catalog và bảng giá tham khảo qua Zalo nhé ạ."

    full_pitch = f"{greeting}\n\n{intro}\n\n{value_prop}\n\n{cta}\n\nChúc anh/chị một ngày làm việc thuận lợi và hiệu quả!"

    # Short SMS / Zalo 1-line version
    sms_version = f"{greeting} em thấy mình cần báo giá {product}. Bên em đang có giá kho tốt giao tận công trình, anh check Zalo em gửi bảng giá nhé ạ!"

    # Call opening script for telesale
    call_script = (
        f"1. Chào hỏi: 'Alo em chào anh {name}, em là chuyên viên bên thiết bị/vật tư xây dựng gọi đến hỗ trợ anh.'\n"
        f"2. Nêu ngữ cảnh: 'Em thấy anh vừa đăng tin tìm hiểu về {product} cho công trình.'\n"
        f"3. Đặt câu hỏi nhu cầu: 'Dạ dự án mình đang cần tiến độ thế nào và khối lượng khoảng bao nhiêu để em hỗ trợ giá kho tốt nhất ạ?'\n"
        f"4. Chốt cuộc gọi: 'Dạ em sẽ kết bạn Zalo số {phone} này để gửi báo giá chi tiết ngay cho anh nhé!'"
    )

    return {
        "zalo_message": full_pitch,
        "sms_message": sms_version,
        "call_guide": call_script
    }
