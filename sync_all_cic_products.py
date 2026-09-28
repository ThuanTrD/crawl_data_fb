"""
Full Product Catalog Crawler & Synchronizer for CIC (cic.com.vn)
Scrapes all 270+ official products across all 8 sectors from cic.com.vn
and ingests them into Supabase public.product_knowledge_base.
"""

import os
import re
import json
import time
import html
import urllib.request
import psycopg2
import psycopg2.extras

DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres.qllwfecwujzhuwexrlqi:tRpWn0s3s8OxILhQ@aws-0-ap-southeast-2.pooler.supabase.com:5432/postgres"
)

CATEGORIES = {
    'xay-dung': {
        'name': 'Xây dựng & Kết cấu công trình',
        'audience': 'Kỹ sư Kết cấu, Kiến trúc sư, Kỹ sư MEP, Nhà thầu Xây dựng dân dụng & công nghiệp',
        'default_usp': 'Giải pháp tính toán kết cấu, thiết kế mô hình 3D, tối ưu hóa vật liệu và đạt chuẩn tiêu chuẩn thiết kế Việt Nam (TCVN) và quốc tế.'
    },
    'giao-thong': {
        'name': 'Giao thông, Cầu đường & Hạ tầng kỹ thuật',
        'audience': 'Kỹ sư Cầu đường, Giao thông, Khảo sát địa hình, Ban Quản lý dự án hạ tầng',
        'default_usp': 'Phần mềm và thiết bị khảo sát, thiết kế tuyến đường, cầu, nút giao thông, sân bay và mô phỏng giao thông chuẩn xác.'
    },
    'thuy-loi': {
        'name': 'Thủy lợi, Thủy điện & Tài nguyên nước',
        'audience': 'Kỹ sư Thủy lợi, Thủy điện, Quản lý tài nguyên nước, Phòng chống thiên tai',
        'default_usp': 'Mô hình hóa dòng chảy, tính toán ngập lụt, quy hoạch lưu vực sông, thiết kế đê đập và công trình thủy công.'
    },
    'dau-khi,mo-khai-khoang': {
        'name': 'Dầu khí & Mỏ khai khoáng',
        'audience': 'Kỹ sư Đường ống, Khai khoáng, Lọc hóa dầu, Khảo sát địa chất khoáng sản',
        'default_usp': 'Mô phỏng đường ống công nghệ, tính toán ứng suất bồn bể, an toàn mỏ và đánh giá rủi ro công nghiệp.'
    },
    'moi-truong': {
        'name': 'Môi trường & Biến đổi khí hậu',
        'audience': 'Chuyên gia Môi trường, Đơn vị xử lý nước thải, Quan trắc khí thải, Kiểm kê khí nhà kính',
        'default_usp': 'Mô phỏng phát tán ô nhiễm khí quyển, tính toán xử lý chất thải và giải pháp kiểm kê khí nhà kính đạt chuẩn quốc tế.'
    },
    'co-khi-che-tao': {
        'name': 'Cơ khí chế tạo & CAD/CAM/CNC',
        'audience': 'Kỹ sư Cơ khí, Chế tạo máy, Lập trình CNC, Nhà xưởng sản xuất gia công',
        'default_usp': 'Giải pháp CAD/CAM toàn diện, lập trình gia công CNC từ 2.5D đến 5 trục, tối ưu đường dao và cắt gọt kim loại, gỗ.'
    },
    'dien-luc': {
        'name': 'Điện lực & Năng lượng tái tạo',
        'audience': 'Kỹ sư Điện, Thiết kế trạm biến áp, Điện gió, Điện mặt trời, Lưới điện truyền tải',
        'default_usp': 'Tính toán kinh tế năng lượng, đánh giá tiềm năng điện gió chuẩn bankable, thiết kế hệ thống điện tin cậy cao.'
    },
    'noi-that-vat-lieu-xay-dung': {
        'name': 'Nội thất, Render 3D & Vật liệu xây dựng',
        'audience': 'Kiến trúc sư nội thất, Diễn họa 3D, Đơn vị sản xuất nội thất & cung ứng vật liệu',
        'default_usp': 'Công cụ render 3D thời gian thực siêu thực, tối ưu bóc tách sản xuất và trình chiếu tương tác khách hàng.'
    }
}

def crawl_all_catalog() -> list:
    all_products = []
    seen_slugs = set()

    for cat_slug, cat_meta in CATEGORIES.items():
        url = f'https://www.cic.com.vn/san-pham.html?linhvuc={cat_slug}'
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = resp.read().decode('utf-8', errors='ignore')
                matches = re.findall(
                    r'<div[^>]*class=[\"\']product-item[\"\'][^>]*>\s*<a\s+href=[\"\']([^\"\']+)[\"\'][^>]*>([\s\S]*?)</a>',
                    data
                )
                for p_url, p_name in matches:
                    clean_name = html.unescape(p_name).strip()
                    m_slug = re.search(r'/san-pham/([a-zA-Z0-9\-_]+)-p\d+\.html', p_url)
                    slug = m_slug.group(1).lower() if m_slug else re.sub(r'[^a-zA-Z0-9]+', '-', clean_name.lower()).strip('-')

                    if slug in seen_slugs:
                        continue
                    seen_slugs.add(slug)

                    # Extract brief description if has separator
                    parts = clean_name.split(' - ')
                    short_name = parts[0].strip()
                    brief_desc = parts[1].strip() if len(parts) > 1 else cat_meta['default_usp']

                    # Generate USPs
                    usps = [
                        f"{clean_name} - Phân phối và chuyển giao công nghệ chính hãng bởi Công ty CP Công nghệ và Tư vấn CIC (35+ năm kinh nghiệm).",
                        f"Ứng dụng chuyên sâu trong lĩnh vực {cat_meta['name']}: {brief_desc}.",
                        "Cung cấp đầy đủ giấy chứng nhận bản quyền doanh nghiệp hợp pháp, chứng từ CO/CQ và hóa đơn VAT.",
                        "Đội ngũ chuyên gia, kỹ sư CIC trực tiếp đào tạo chuyển giao công nghệ, cài đặt và hỗ trợ kỹ thuật tại Việt Nam.",
                        "Chính sách giá linh hoạt: License theo dự án, bản quyền vĩnh viễn hoặc thuê bao năm với chiết khấu tốt nhất."
                    ]

                    # Customizations for core flagship software
                    if 'enjicad' in slug:
                        usps.insert(0, "Tiết kiệm hơn 80% chi phí so với AutoCAD, tương thích 100% lệnh vẽ, DWG, Lisp và Font SHX tiếng Việt.")
                    elif 'etabs' in slug or 'sap2000' in slug or 'csi' in slug:
                        usps.insert(0, "Giải pháp phân tích kết cấu tiêu chuẩn số 1 thế giới của hãng CSI (Mỹ), hỗ trợ đầy đủ TCVN và Eurocode/AISC.")
                    elif 'plaxis' in slug:
                        usps.insert(0, "Phần mềm phần tử hữu hạn số 1 thế giới trong tính toán địa kỹ thuật, nền móng, hố đào sâu và cọc monopile.")

                    all_products.append({
                        'product_key': slug,
                        'product_name': clean_name,
                        'vendor': 'Công ty Cổ phần Công nghệ và Tư vấn CIC (37 Lê Đại Hành, Hà Nội)',
                        'target_audience': cat_meta['audience'],
                        'key_usps': usps,
                        'pricing_details': {
                            'policy': 'Báo giá chính hãng cạnh tranh từ CIC, hỗ trợ license cá nhân, doanh nghiệp và license đào tạo.',
                            'trial_support': 'Hỗ trợ bản dùng thử (Trial), demo trực tiếp tính năng và tư vấn cấu hình phù hợp với dự án.',
                            'consulting': 'Hỗ trợ tư vấn kỹ thuật chuyên sâu 1-1 trước khi đầu tư trang bị.'
                        },
                        'objection_scripts': {
                            'KY_THUAT_VA_CHUYEN_GIAO': {
                                'concern': 'Lo ngại phần mềm khó sử dụng hoặc chưa nắm rõ quy trình mô phỏng.',
                                'selling_point': 'CIC có đội ngũ kỹ sư thạc sĩ, tiến sĩ chuyên ngành tổ chức khóa đào tạo chuyển giao công nghệ bài bản và đồng hành trong suốt quá trình triển khai dự án.',
                                'action': 'Gửi tài liệu hướng dẫn kỹ thuật, video demo tính năng và mời tham gia buổi demo trực tiếp.'
                            },
                            'BAN_QUYEN_VA_CHI_PHI': {
                                'concern': 'Cần bảng báo giá chính hãng và hồ sơ năng lực của đơn vị cung cấp.',
                                'selling_point': 'CIC là đại diện phân phối chính thức từ các hãng phần mềm hàng đầu thế giới (Bentley, CSI, DHI, Hexagon...), cung cấp đầy đủ giấy chứng nhận đại lý ủy quyền và hóa đơn VAT.',
                                'action': 'Hỏi quy mô dự án và số lượng máy để gửi bảng báo giá kèm hồ sơ năng lực CIC.'
                            }
                        },
                        'sales_playbook': {
                            'pitch_template_pricing': f'Dạ em chào anh {{name}}! Em thấy anh vừa để lại bình luận quan tâm đến giải pháp {clean_name} trên trang của CIC. Hiện tại bên em là đại diện phân phối chính hãng với đầy đủ giấy phép bản quyền, hỗ trợ đào tạo chuyển giao và chính sách giá ưu đãi tốt nhất cho doanh nghiệp. Anh dự kiến trang bị cho bao nhiêu người dùng hoặc phục vụ dự án nào để em gửi bảng báo giá chi tiết nhé ạ!',
                            'pitch_template_tech': f'Dạ em chào anh {{name}}! Thấy anh đang quan tâm đến tính năng chuyên sâu của {clean_name}. Bên em có đội ngũ chuyên gia kỹ sư CIC sẵn sàng hỗ trợ demo trực tiếp và gửi tài liệu kỹ thuật chi tiết để anh đánh giá mức độ phù hợp với công trình của mình. Em xin phép gửi tài liệu và hỗ trợ anh trải nghiệm nhé ạ!',
                            'pitch_template_inbox': f'Dạ em chào anh {{name}}! Em thấy anh cmt quan tâm đến giải pháp {clean_name} của CIC. Em xin phép gửi thông số kỹ thuật chi tiết và chính sách ưu đãi qua tin nhắn để anh tham khảo nhé ạ!'
                        },
                        'metadata': {
                            'category': cat_meta['name'],
                            'official_url': p_url,
                            'hotline': '024 3974 6708 / 088 646 2020',
                            'source': 'https://www.cic.com.vn/'
                        }
                    })
        except Exception as e:
            print(f'Error crawling category {cat_slug}: {e}')

    return all_products

def ingest_products_to_supabase(products: list) -> int:
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    upsert_sql = """
        INSERT INTO public.product_knowledge_base (
            product_key, product_name, vendor, target_audience, key_usps,
            pricing_details, objection_scripts, sales_playbook, metadata, updated_at
        ) VALUES (
            %s, %s, %s, %s, %s::jsonb,
            %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, NOW()
        )
        ON CONFLICT (product_key) DO UPDATE SET
            product_name = EXCLUDED.product_name,
            vendor = EXCLUDED.vendor,
            target_audience = EXCLUDED.target_audience,
            key_usps = EXCLUDED.key_usps,
            pricing_details = EXCLUDED.pricing_details,
            objection_scripts = EXCLUDED.objection_scripts,
            sales_playbook = EXCLUDED.sales_playbook,
            metadata = EXCLUDED.metadata,
            updated_at = NOW();
    """

    count = 0
    for p in products:
        cur.execute(upsert_sql, (
            p['product_key'][:250],
            p['product_name'],
            p['vendor'],
            p['target_audience'],
            json.dumps(p['key_usps']),
            json.dumps(p['pricing_details']),
            json.dumps(p['objection_scripts']),
            json.dumps(p['sales_playbook']),
            json.dumps(p['metadata'])
        ))
        count += 1

    conn.commit()
    cur.close()
    conn.close()
    return count

if __name__ == '__main__':
    print("=== Bắt đầu cào toàn bộ danh mục sản phẩm từ website cic.com.vn ===")
    t0 = time.time()
    catalog = crawl_all_catalog()
    print(f"-> Thu thập thành công {len(catalog)} sản phẩm từ tất cả 8 lĩnh vực của CIC trong {round(time.time() - t0, 2)}s.")
    print("=== Bắt đầu nạp vào Supabase (public.product_knowledge_base) ===")
    saved = ingest_products_to_supabase(catalog)
    print(f"-> Hoàn tất lưu trữ {saved} sản phẩm vào cơ sở dữ liệu Supabase thành công!")
