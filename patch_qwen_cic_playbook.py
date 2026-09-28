with open("/home/ADMIN/qwen_sales_agent.py", "r", encoding="utf-8") as f:
    code = f.read()

# Update prompt to explicitly use verified CIC website data
old_prompt_section = """            qwen_prompt = f\"\"\"Dựa vào thông tin sản phẩm trong cơ sở dữ liệu:
Sản phẩm: {prod_name}
Ưu điểm: {', '.join(usps[:3])}
Chính sách giá: {json.dumps(pricing, ensure_ascii=False)}

Khách hàng: {cust['author_name']}
Bình luận của khách: \"{full_text}\"
Nhu cầu / Khúc mắc: {pain_point}

Hãy viết 1 câu tin nhắn Messenger cực kỳ thân thiện, tự nhiên và thuyết phục khách mua hoặc dùng thử sản phẩm {prod_name}. Viết ngắn gọn 2-3 câu, xưng hô Em - {first_name}.\"\"\""""

new_prompt_section = """            playbook = self.knowledge.get("sales_playbook", {})
            vendor = self.knowledge.get("vendor", "Công ty Cổ phần Công nghệ và Tư vấn CIC")
            
            qwen_prompt = f\"\"\"Bạn là chuyên viên tư vấn bán hàng giải pháp phần mềm kỹ thuật của {vendor}.
Thông tin chính thức từ website cic.com.vn và enjicad.vn:
- Sản phẩm: {prod_name}
- Tiết kiệm: Hơn 80% chi phí so với AutoCAD chính hãng.
- Hình thức cấp phép: Bản quyền Vĩnh viễn (Perpetual - trả 1 lần dùng trọn đời), Thuê bao năm (Annual), hoặc Network License cho công ty.
- Điểm mạnh kỹ thuật: Tương thích 100% AutoCAD (DWG, lệnh vẽ, phím tắt, Lisp, Font SHX tiếng Việt). enjiCAD 2027 mới nhất mở mượt file >150MB, có Point Cloud, Dynamic Blocks, Drawing Compare.
- Hỗ trợ: Kỹ sư CIC hỗ trợ kỹ thuật trực tiếp bằng tiếng Việt, tặng key Trial 30 ngày tại enjicad.vn.

Khách hàng: {cust['author_name']} ({first_name})
Bình luận của khách: \"{full_text}\"
Nhu cầu / Khúc mắc: {pain_point}

Nhiệm vụ: Viết 1 tin nhắn Messenger tư vấn chân thành, tự nhiên, đánh trúng nhu cầu khách hàng dựa trên thông tin chính thức của CIC ở trên. Kêu gọi hành động gửi báo giá hoặc link tải Trial 30 ngày. Xưng hô Em - Anh/Chị {first_name}. Viết ngắn gọn 3-4 câu.\"\"\""""

code = code.replace(old_prompt_section, new_prompt_section)

# Update fallback deterministic scripts with exact cic.com.vn details
old_fallback = """                if sub_intent == "PRICING_LICENSING":
                    qwen_pitch = (
                        f"Dạ em chào anh {first_name}! Em thấy anh vừa để lại bình luận quan tâm đến chi phí bản quyền {prod_name}. "
                        f"Hiện tại bên em đang có chính sách giá ưu đãi tiết kiệm đến 70% so với AutoCAD (chỉ bằng khoảng 1/4), "
                        f"đầy đủ chứng nhận bản quyền doanh nghiệp hợp pháp và hỗ trợ cả gói thuê bao năm lẫn mua đứt vĩnh viễn. "
                        f"Anh dự kiến trang bị cho bao nhiêu máy để em gửi bảng báo giá chiết khấu tốt nhất cho công ty mình nhé ạ!"
                    )
                elif sub_intent == "TECHNICAL_INQUIRY":
                    qwen_pitch = (
                        f"Dạ em chào anh {first_name}! Thấy anh đang băn khoăn về độ mượt của bản vẽ và hỗ trợ LISP / Font tiếng Việt. "
                        f"{prod_name} tối ưu nhân đồ họa mở cực mượt các file DWG dung lượng trên 150MB không bị giật lag và tương thích 100% Lisp của AutoCAD. "
                        f"Em xin phép gửi anh link tải bản dùng thử (Trial) 30 ngày full tính năng để anh mở trực tiếp file dự án của mình trải nghiệm nhé ạ!"
                    )
                elif sub_intent == "DIRECT_INBOX_REQUEST":
                    qwen_pitch = (
                        f"Dạ em chào anh {first_name}! Em thấy anh cmt '{full_text}' quan tâm đến phần mềm {prod_name} của CIC. "
                        f"Em xin phép gửi anh bảng giá chi tiết và brochure so sánh tính năng thay thế AutoCAD qua Messenger. "
                        f"Anh đang cần trang bị cho máy cá nhân hay văn phòng thiết kế để em tư vấn gói phù hợp nhất nhé ạ!"
                    )
                else:
                    qwen_pitch = (
                        f"Dạ em chào anh {first_name}! Cảm ơn anh đã quan tâm đến giải pháp {prod_name}. "
                        f"Em xin phép gửi anh tài liệu tính năng phần mềm và link tải bản dùng thử 30 ngày để anh trải nghiệm thực tế nhé ạ!"
                    )"""

new_fallback = """                if sub_intent == "PRICING_LICENSING":
                    qwen_pitch = (
                        f"Dạ em chào anh {first_name}! Em thấy anh vừa để lại bình luận quan tâm đến chi phí bản quyền {prod_name} trên bài viết của CIC. "
                        f"Hiện tại bên em đang có chính sách giá ưu đãi tiết kiệm hơn 80% so với AutoCAD, hỗ trợ cả giấy phép Vĩnh viễn (mua 1 lần dùng trọn đời) "
                        f"lẫn gói Thuê bao năm và bản quyền Network cho nhiều máy trong công ty, đầy đủ chứng nhận bản quyền doanh nghiệp hợp pháp từ CIC và hóa đơn VAT. "
                        f"Anh dự kiến trang bị cho bao nhiêu máy để em gửi bảng báo giá chiết khấu tốt nhất cho công ty mình nhé ạ!"
                    )
                elif sub_intent == "TECHNICAL_INQUIRY":
                    qwen_pitch = (
                        f"Dạ em chào anh {first_name}! Thấy anh đang băn khoăn về độ mượt khi mở bản vẽ nặng và tương thích Lisp/Font tiếng Việt. "
                        f"Phiên bản enjiCAD 2027 mới nhất của CIC đã tối ưu hóa nhân đồ họa tăng tốc phần cứng, mở cực mượt các file DWG dung lượng lớn (>150MB) "
                        f"và cam kết tương thích 100% với toàn bộ Lisp, VLISP, Font SHX tiếng Việt của AutoCAD mà không cần sửa code. "
                        f"Em xin phép gửi anh link tải bản dùng thử 30 ngày full tính năng tại enjicad.vn để anh mở thử trực tiếp file dự án của mình trải nghiệm nhé ạ!"
                    )
                elif sub_intent == "DIRECT_INBOX_REQUEST":
                    qwen_pitch = (
                        f"Dạ em chào anh {first_name}! Em thấy anh cmt '{full_text}' quan tâm đến phần mềm {prod_name} của Công ty CIC. "
                        f"Em xin phép gửi anh tài liệu so sánh tính năng enjiCAD với AutoCAD kèm bảng chào giá ưu đãi tiết kiệm hơn 80% qua tin nhắn để anh tham khảo nhé ạ! "
                        f"Anh đang cần trang bị cho cá nhân hay văn phòng thiết kế của công ty ạ?"
                    )
                else:
                    qwen_pitch = (
                        f"Dạ em chào anh {first_name}! Cảm ơn anh đã quan tâm đến giải pháp {prod_name} của Công ty CP Công nghệ và Tư vấn CIC. "
                        f"Em xin phép gửi anh brochure chi tiết các tính năng mới của enjiCAD 2027 và link tải bản dùng thử 30 ngày để anh trải nghiệm thực tế nhé ạ!"
                    )"""

code = code.replace(old_fallback, new_fallback)

# Update telesale script
old_tele = 'telesale = f"Alo em chào anh {first_name}, em là nhân viên tư vấn phần mềm {prod_name} của công ty CIC. Em thấy anh vừa để lại bình luận \'{full_text}\' trên Facebook nên em gọi hỗ trợ tư vấn ngay cho anh..."'
new_tele = 'telesale = f"Dạ alo em chào anh {first_name}, em là chuyên viên tư vấn giải pháp bản quyền {prod_name} từ Công ty Cổ phần Công nghệ và Tư vấn CIC (37 Lê Đại Hành, Hà Nội). Em thấy anh vừa để lại bình luận \'{full_text}\' trên Facebook nên em liên hệ hỗ trợ tư vấn và gửi link dùng thử 30 ngày ngay cho anh..."'
code = code.replace(old_tele, new_tele)

with open("/home/ADMIN/qwen_sales_agent.py", "w", encoding="utf-8") as f:
    f.write(code)

print("Updated qwen_sales_agent.py with official CIC website facts successfully!")
