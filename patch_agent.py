import re

with open('/home/ADMIN/qwen_sales_agent.py', 'r', encoding='utf-8') as f:
    text = f.read()

# We will add generate_pitch_with_qwen function and update analyze_and_pitch
# to strictly respect user's rule:
# "cào thông tin khách hàng cmt trên fb theo key cung cấp, còn việc sinh được lời thoại hay không sẽ do qwen với database xử lý"
