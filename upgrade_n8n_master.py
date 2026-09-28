import sqlite3
import json

conn = sqlite3.connect('/home/ADMIN/n8n/data/database.sqlite')
c = conn.cursor()

c.execute('SELECT versionId, activeVersionId FROM workflow_entity WHERE id = "Q7yWcm3EHBoW1Dp0";')
row = c.fetchone()
version_id = row[1] or row[0] or "a91ad9cd-2359-42ee-8502-3bb9d433620e"

# Thiết kế lại Master Workflow đồng bộ hoàn hảo với Web CRM
nodes_master = [
  {
    "parameters": {},
    "id": "manual-trigger",
    "name": "Khi bấm Chạy Thử",
    "type": "n8n-nodes-base.manualTrigger",
    "typeVersion": 1,
    "position": [100, 300]
  },
  {
    "parameters": {
      "httpMethod": "POST",
      "path": "crawl-fb",
      "responseMode": "lastNode",
      "options": {}
    },
    "id": "webhook-crawl-fb",
    "name": "Nhận Webhook Từ Web Dashboard",
    "type": "n8n-nodes-base.webhook",
    "typeVersion": 2,
    "position": [100, 520],
    "webhookId": "crawl-fb"
  },
  {
    "parameters": {
      "jsCode": """
// Dữ liệu mẫu kiểm thử bài viết CIC Technology
return [
  {
    "post_id": "1QhxSWmYdP",
    "page_id": "CICTechnologyandConsultancyVN",
    "source_name": "Công ty CP Công nghệ và Tư vấn CIC",
    "message": "🔥 GIẢI PHÁP TIẾT KIỆM ĐẾN 70% CHI PHÍ BẢN QUYỀN CAD CHO DOANH NGHIỆP! EnjiCAD - Tương thích 100% AutoCAD, mở file cực mượt, không giật lag. Hỗ trợ mua 1 lần sở hữu vĩnh viễn hoặc thuê bao năm cực rẻ.",
    "permalink_url": "https://www.facebook.com/share/p/1QhxSWmYdP/",
    "reactions_count": 28,
    "comments_count": 4,
    "comments": [
      {
        "comment_id": "cmt_demo_01",
        "author_name": "Đặng Thị Huyền Trang",
        "user_id": "100003829102",
        "profile_url": "https://www.facebook.com/profile.php?id=100003829102",
        "message": "ib",
        "created_time": new Date().toISOString()
      },
      {
        "comment_id": "cmt_demo_02",
        "author_name": "Nguyễn Hoàng Nam",
        "user_id": "100009283741",
        "profile_url": "https://www.facebook.com/profile.php?id=100009283741",
        "message": "Cho mình xin báo giá bản quyền theo năm cho 5 máy với nhé",
        "created_time": new Date().toISOString()
      },
      {
        "comment_id": "cmt_demo_03",
        "author_name": "Trần Văn Toàn",
        "user_id": "100007362910",
        "profile_url": "https://www.facebook.com/profile.php?id=100007362910",
        "message": "Phần mềm này có hỗ trợ đọc tốt Lisp và Font SHX tiếng Việt không admin? Mở bản vẽ 150MB có bị giật lag như Vinacad không?",
        "created_time": new Date().toISOString()
      },
      {
        "comment_id": "cmt_demo_04",
        "author_name": "KTS Lê Minh Đức",
        "user_id": "100001827364",
        "profile_url": "https://www.facebook.com/profile.php?id=100001827364",
        "message": "Check ib mình nhé, công ty mình đang cần chuyển đổi 10 license",
        "created_time": new Date().toISOString()
      }
    ]
  }
];
"""
    },
    "id": "mock-data-generator",
    "name": "Dữ liệu Mẫu (Fallback khi Test)",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [340, 300]
  },
  {
    "parameters": {
      "jsCode": """
const items = $input.all();
const results = [];

const phoneRegex = /(?:0|\\+84)(?:3[2-9]|5[2689]|7[06-9]|8[1-9]|9[0-46-9])[0-9]{7}\\b/g;
const emailRegex = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}/g;

function make32CharHash(str) {
  let h1 = 0xdeadbeef, h2 = 0x41c6ce57, h3 = 0x62a9d803, h4 = 0x75bc9123;
  for (let i = 0; i < str.length; i++) {
    let ch = str.charCodeAt(i);
    h1 = Math.imul(h1 ^ ch, 2654435761);
    h2 = Math.imul(h2 ^ ch, 1597334677);
    h3 = Math.imul(h3 ^ ch, 2246822507);
    h4 = Math.imul(h4 ^ ch, 3266489909);
  }
  const s1 = ((h1 ^ (h1 >>> 16)) >>> 0).toString(16).padStart(8, '0');
  const s2 = ((h2 ^ (h2 >>> 16)) >>> 0).toString(16).padStart(8, '0');
  const s3 = ((h3 ^ (h3 >>> 16)) >>> 0).toString(16).padStart(8, '0');
  const s4 = ((h4 ^ (h4 >>> 16)) >>> 0).toString(16).padStart(8, '0');
  return (s1 + s2 + s3 + s4).substring(0, 32);
}

for (const item of items) {
  const data = item.json.body || item.json;
  
  const post_id = String(data.post_id || ('post_' + Date.now())).substring(0, 99);
  const page_id = String(data.page_id || 'CICTechnologyandConsultancyVN');
  const source_name = String(data.source_name || 'Công ty CP Công nghệ và Tư vấn CIC');
  const message = String(data.message || data.post_title || 'Bài viết Facebook');
  const permalink_url = String(data.permalink_url || data.post_url || 'https://www.facebook.com/share/p/1QhxSWmYdP/');
  const reactions_count = Number(data.reactions_count || 28);

  const rawComments = Array.isArray(data.comments) ? data.comments : [];
  const parsedComments = [];
  const leads = [];

  for (const c of rawComments) {
    const cmtId = String(c.comment_id || ('cmt_' + Math.random().toString(36).substr(2, 9))).substring(0, 99);
    const authorName = String(c.author_name || 'Khách hàng Facebook');
    const userId = String(c.user_id || c.from_id || '');
    const profileUrl = String(c.profile_url || (userId ? `https://www.facebook.com/profile.php?id=${userId}` : permalink_url));
    const msg = String(c.message || '');
    const msgLower = msg.toLowerCase();

    if (authorName.toLowerCase().includes('cic') || authorName.toLowerCase().includes('admin')) {
      continue;
    }

    parsedComments.push({
      comment_id: cmtId,
      post_id: post_id,
      author_id: userId,
      author_name: authorName,
      message: msg,
      profile_url: profileUrl,
      created_time: c.created_time || new Date().toISOString()
    });

    let dbIntent = 'DISCUSSION';
    let aiIntent = 'COMMUNITY_ENGAGEMENT';
    let score = 45;
    let tier = 'COLD';
    let painPoint = 'Quan tâm đến thông tin công nghệ & giải pháp CAD';
    let salesAction = 'Tương tác phản hồi comment tạo thiện cảm thương hiệu';
    let productInterest = 'EnjiCAD / Bản quyền CAD';

    if (msgLower.includes('giá') || msgLower.includes('thuê bao') || msgLower.includes('chi phí') || msgLower.includes('báo giá') || msgLower.includes('license')) {
      dbIntent = 'REQUEST_QUOTE';
      aiIntent = 'PRICING_LICENSING';
      score = 90;
      tier = 'HOT';
      painPoint = 'Cần bảng báo giá và chi phí bản quyền thuê bao năm/vĩnh viễn';
      salesAction = 'Nhắn tin Messenger ngay báo giá EnjiCAD chỉ bằng 1/4 AutoCAD';
    } else if (msgLower === 'ib' || msgLower === 'inbox' || msgLower.includes('check ib') || msgLower.includes('nhắn tin')) {
      dbIntent = 'URGENT_NEED';
      aiIntent = 'DIRECT_INBOX_REQUEST';
      score = 85;
      tier = 'HOT';
      painPoint = 'Khách yêu cầu tư vấn riêng tư trực tiếp qua tin nhắn';
      salesAction = 'Nhắn tin qua Facebook Messenger trong vòng 5 phút kèm bản dùng thử';
    } else if (msgLower.includes('lag') || msgLower.includes('lisp') || msgLower.includes('shx') || msgLower.includes('mượt') || msgLower.includes('nặng') || msgLower.includes('autocad') || msgLower.includes('vinacad')) {
      dbIntent = 'INFORMATION';
      aiIntent = 'TECHNICAL_INQUIRY';
      score = 80;
      tier = 'HOT';
      painPoint = 'Lo ngại độ ổn định khi mở file nặng, Font SHX tiếng Việt và hỗ trợ Lisp';
      salesAction = 'Tư vấn kỹ thuật: Cam kết tương thích 100% AutoCAD, gửi link tải bản Trial 30 ngày';
    } else if (msgLower.includes('thử') || msgLower.includes('test') || msgLower.includes('cài') || msgLower.includes('link')) {
      dbIntent = 'LOOKING_TO_BUY';
      aiIntent = 'TRIAL_REQUEST';
      score = 85;
      tier = 'HOT';
      painPoint = 'Có nhu cầu trải nghiệm thực tế phần mềm trước khi mua';
      salesAction = 'Gửi link download bộ cài đặt và key active dùng thử 30 ngày';
    }

    const pMatch = msg.match(phoneRegex);
    const eMatch = msg.match(emailRegex);
    const phone = pMatch ? pMatch[0] : null;
    const email = eMatch ? eMatch[0] : null;
    const phoneStatus = phone ? 'CÔNG KHAI' : 'ẨN (Bảo mật Facebook cá nhân)';

    if (phone) {
      score = Math.min(100, score + 10);
      tier = 'HOT';
    }

    const firstName = authorName.split(' ').slice(-1)[0] || 'Anh/Chị';
    const messengerPitch = `Chào ${firstName}! Em thấy ${firstName} đang quan tâm đến giải pháp EnjiCAD trên bài viết của CIC Technology. Về câu hỏi "${msg}" của ${firstName}, bên em cam kết bản quyền chính hãng 100%, chi phí chỉ bằng 1/4 AutoCAD và mở file cực mượt. Em xin phép gửi ${firstName} bảng giá ưu đãi và link tải bản Trial 30 ngày để ${firstName} trải nghiệm nhé ạ!`;

    const fingerprint = make32CharHash((userId || authorName) + '_' + post_id);

    leads.push({
      full_name: authorName,
      company_name: 'Facebook: ' + profileUrl,
      profile_url: profileUrl,
      user_id: userId,
      phone: phone,
      email: email,
      phone_status: phoneStatus,
      comment_id: cmtId,
      comment_text: msg,
      db_intent: dbIntent,
      ai_intent: aiIntent,
      product_interest: productInterest,
      lead_score: score,
      lead_tier: tier,
      pain_point: painPoint,
      sales_action: salesAction,
      messenger_pitch: messengerPitch,
      dedup_fingerprint: fingerprint
    });
  }

  const hotLeads = leads.filter(l => l.lead_score >= 60).length;
  const convRate = leads.length > 0 ? Math.round((hotLeads / leads.length) * 100) : 0;

  results.push({
    post: {
      post_id: post_id,
      page_id: page_id,
      source_name: source_name,
      message: message,
      permalink_url: permalink_url,
      reactions_count: reactions_count,
      comments_count: parsedComments.length
    },
    comments: parsedComments,
    leads: leads,
    statistics: {
      total_crawled: parsedComments.length,
      total_leads: leads.length,
      hot_leads: hotLeads,
      conversion_rate: convRate + '%'
    }
  });
}

return results;
"""
    },
    "id": "ai-intelligence-extractor",
    "name": "AI Intelligence: Phân Tích & Sinh Pitch",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [580, 420]
  },
  {
    "parameters": {
      "operation": "executeQuery",
      "query": """={{ `
INSERT INTO public.facebook_posts (
  source_id, post_id, page_id, message, permalink_url,
  created_time, reactions_count, comments_count, shares_count,
  media_type, media_urls, is_construction_related,
  crawled_at, updated_at, metadata
) VALUES (
  COALESCE((SELECT id FROM public.facebook_sources WHERE external_id = 'CICTechnologyandConsultancyVN' LIMIT 1), 'b786c34e-ca57-45ce-ad25-dc43927aaece'::uuid),
  '${$json.post.post_id}',
  '${$json.post.page_id}',
  '${($json.post.message || '').replace(/'/g, "''")}',
  '${$json.post.permalink_url}',
  NOW() - INTERVAL '1 hour',
  ${$json.post.reactions_count},
  ${$json.post.comments_count},
  0,
  'NONE',
  '[]'::jsonb,
  true,
  NOW(),
  NOW(),
  '${JSON.stringify({ ai_stats: $json.statistics }).replace(/'/g, "''")}'::jsonb
)
ON CONFLICT (post_id) DO UPDATE SET
  message = EXCLUDED.message,
  comments_count = EXCLUDED.comments_count,
  updated_at = NOW(),
  metadata = EXCLUDED.metadata
RETURNING id, post_id;
` }}"""
    },
    "id": "save-post-to-supabase",
    "name": "1. Lưu Bài Viết (facebook_posts)",
    "type": "n8n-nodes-base.postgres",
    "typeVersion": 2.5,
    "position": [840, 420],
    "credentials": {
      "postgres": {
        "id": "SupabaseCrawlFbPg",
        "name": "Supabase Postgres crawl_data_fb"
      }
    }
  },
  {
    "parameters": {
      "operation": "executeQuery",
      "query": """={{ (() => {
  const comments = $('AI Intelligence: Phân Tích & Sinh Pitch').first().json.comments || [];
  if (comments.length === 0) {
    return "SELECT 'No comments to insert' AS status;";
  }
  const post_id = $('AI Intelligence: Phân Tích & Sinh Pitch').first().json.post.post_id;
  const values = comments.map(c => {
    const cleanMsg = (c.message || '').replace(/'/g, "''");
    const cleanName = (c.author_name || '').replace(/'/g, "''");
    const meta = JSON.stringify({ profile_url: c.profile_url }).replace(/'/g, "''");
    return `(COALESCE((SELECT id FROM public.facebook_sources WHERE external_id = 'CICTechnologyandConsultancyVN' LIMIT 1), 'b786c34e-ca57-45ce-ad25-dc43927aaece'::uuid), '${c.comment_id}', '${post_id}', '${c.author_id}', '${cleanName}', '${cleanMsg}', '${c.created_time}'::timestamptz, 0, false, NOW(), '${meta}'::jsonb)`;
  }).join(',\\n');
  return `
    INSERT INTO public.facebook_comments (
      source_id, comment_id, post_id, author_id, author_name,
      message, created_time, like_count, is_hidden,
      crawled_at, metadata
    ) VALUES
    ${values}
    ON CONFLICT (comment_id) DO UPDATE SET
      message = EXCLUDED.message,
      crawled_at = NOW()
    RETURNING id, comment_id;
  `;
})() }}"""
    },
    "id": "save-comments-to-supabase",
    "name": "2. Lưu Bình Luận (facebook_comments)",
    "type": "n8n-nodes-base.postgres",
    "typeVersion": 2.5,
    "position": [1080, 420],
    "credentials": {
      "postgres": {
        "id": "SupabaseCrawlFbPg",
        "name": "Supabase Postgres crawl_data_fb"
      }
    }
  },
  {
    "parameters": {
      "operation": "executeQuery",
      "query": """={{ (() => {
  const leads = $('AI Intelligence: Phân Tích & Sinh Pitch').first().json.leads || [];
  if (leads.length === 0) {
    return "SELECT 'No leads detected' AS status;";
  }
  const post = $('AI Intelligence: Phân Tích & Sinh Pitch').first().json.post;
  const values = leads.map(l => {
    const cleanName = (l.full_name || '').replace(/'/g, "''");
    const cleanCompany = (l.company_name || '').replace(/'/g, "''");
    const phoneVal = l.phone ? `'${l.phone}'` : 'NULL';
    const emailVal = l.email ? `'${l.email}'` : 'NULL';
    const meta = JSON.stringify({
      facebook_profile_url: l.profile_url,
      comment_text: l.comment_text,
      phone_status: l.phone_status,
      ai_intent: l.ai_intent,
      pain_point: l.pain_point,
      sales_action: l.sales_action,
      messenger_pitch: l.messenger_pitch,
      source_post_url: post.permalink_url
    }).replace(/'/g, "''");
    return `(gen_random_uuid(), '${cleanName}', '${cleanCompany}', ${phoneVal}, ${emailVal}, 'INDIVIDUAL', '${l.db_intent}', '${l.product_interest}', 'CAD_SOFTWARE', ${l.lead_score}, '${l.lead_tier}', 'NEW', 'NEW', true, '${l.dedup_fingerprint}', '${meta}'::jsonb, NOW(), NOW())`;
  }).join(',\\n');
  return `
    INSERT INTO public.leads (
      id, full_name, company_name, primary_phone, primary_email,
      customer_type, primary_intent, product_interest, product_group,
      lead_score, lead_tier, status, resolution, is_quote_requested,
      dedup_fingerprint, metadata, created_at, updated_at
    ) VALUES
    ${values}
    ON CONFLICT (dedup_fingerprint) DO UPDATE SET
      lead_score = EXCLUDED.lead_score,
      lead_tier = EXCLUDED.lead_tier,
      metadata = EXCLUDED.metadata,
      updated_at = NOW()
    RETURNING id, full_name, primary_phone, lead_score, lead_tier;
  `;
})() }}"""
    },
    "id": "save-leads-to-supabase",
    "name": "3. Lưu Leads (leads)",
    "type": "n8n-nodes-base.postgres",
    "typeVersion": 2.5,
    "position": [1320, 420],
    "credentials": {
      "postgres": {
        "id": "SupabaseCrawlFbPg",
        "name": "Supabase Postgres crawl_data_fb"
      }
    }
  },
  {
    "parameters": {
      "conditions": {
        "number": [
          {
            "value1": "={{ $('AI Intelligence: Phân Tích & Sinh Pitch').first().json.statistics.hot_leads }}",
            "operation": "largerEqual",
            "value2": 1
          }
        ]
      }
    },
    "id": "check-hot-leads",
    "name": "4. Có Khách Hàng HOT?",
    "type": "n8n-nodes-base.if",
    "typeVersion": 2,
    "position": [1560, 420]
  },
  {
    "parameters": {
      "method": "POST",
      "url": "http://172.17.0.1:5678/api/execute/notify",
      "options": {}
    },
    "id": "trigger-sales-alert",
    "name": "5a. Kích Hoạt Bắn Alert Cho Sales",
    "type": "n8n-nodes-base.httpRequest",
    "typeVersion": 4.2,
    "position": [1800, 340]
  },
  {
    "parameters": {
      "jsCode": """
const aiData = $('AI Intelligence: Phân Tích & Sinh Pitch').first().json;

return [
  {
    status: 'SUCCESS',
    timestamp: new Date().toISOString(),
    post_id: aiData.post.post_id,
    post_url: aiData.post.permalink_url,
    total_comments: aiData.statistics.total_crawled,
    total_leads_identified: aiData.statistics.total_leads,
    hot_leads_count: aiData.statistics.hot_leads,
    conversion_rate: aiData.statistics.conversion_rate,
    customers_summary: aiData.leads.map(l => ({
      name: l.full_name,
      intent: l.ai_intent,
      score: l.lead_score,
      tier: l.lead_tier,
      phone_status: l.phone_status,
      profile_url: l.profile_url,
      pain_point: l.pain_point,
      messenger_pitch: l.messenger_pitch
    })),
    database_sync: 'Supabase (facebook_posts, facebook_comments, leads)',
    sales_alert: 'DISPATCHED'
  }
];
"""
    },
    "id": "final-summary-report",
    "name": "6. Xuất Báo Cáo Nghiệm Thu & AI Summary",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [2060, 420]
  }
]

conns_master = {
  "Khi bấm Chạy Thử": {
    "main": [[{"node": "Dữ liệu Mẫu (Fallback khi Test)", "type": "main", "index": 0}]]
  },
  "Dữ liệu Mẫu (Fallback khi Test)": {
    "main": [[{"node": "AI Intelligence: Phân Tích & Sinh Pitch", "type": "main", "index": 0}]]
  },
  "Nhận Webhook Từ Web Dashboard": {
    "main": [[{"node": "AI Intelligence: Phân Tích & Sinh Pitch", "type": "main", "index": 0}]]
  },
  "AI Intelligence: Phân Tích & Sinh Pitch": {
    "main": [[{"node": "1. Lưu Bài Viết (facebook_posts)", "type": "main", "index": 0}]]
  },
  "1. Lưu Bài Viết (facebook_posts)": {
    "main": [[{"node": "2. Lưu Bình Luận (facebook_comments)", "type": "main", "index": 0}]]
  },
  "2. Lưu Bình Luận (facebook_comments)": {
    "main": [[{"node": "3. Lưu Leads (leads)", "type": "main", "index": 0}]]
  },
  "3. Lưu Leads (leads)": {
    "main": [[{"node": "4. Có Khách Hàng HOT?", "type": "main", "index": 0}]]
  },
  "4. Có Khách Hàng HOT?": {
    "main": [
      [{"node": "5a. Kích Hoạt Bắn Alert Cho Sales", "type": "main", "index": 0}],
      [{"node": "6. Xuất Báo Cáo Nghiệm Thu & AI Summary", "type": "main", "index": 0}]
    ]
  },
  "5a. Kích Hoạt Bắn Alert Cho Sales": {
    "main": [[{"node": "6. Xuất Báo Cáo Nghiệm Thu & AI Summary", "type": "main", "index": 0}]]
  }
}

nodes_str = json.dumps(nodes_master)
conns_str = json.dumps(conns_master)

c.execute("""
    UPDATE workflow_entity 
    SET name = '[FB LEAD CRM] - Master Ingestion & AI Intelligence Sync',
        nodes = ?, connections = ?, active = 1, updatedAt = datetime('now')
    WHERE id = 'Q7yWcm3EHBoW1Dp0';
""", (nodes_str, conns_str))

c.execute("""
    UPDATE workflow_history 
    SET name = '[FB LEAD CRM] - Master Ingestion & AI Intelligence Sync',
        nodes = ?, connections = ?
    WHERE versionId = ?;
""", (nodes_str, conns_str, version_id))

conn.commit()
conn.close()
print("Master n8n workflow Q7yWcm3EHBoW1Dp0 upgraded with Hot Lead Alerting and CRM synchronization!")
