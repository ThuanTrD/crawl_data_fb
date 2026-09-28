with open('/home/ADMIN/qwen_sales_agent.py', 'r', encoding='utf-8') as f:
    text = f.read()

old_pipeline = '''def run_keyword_pipeline(keyword: str = "enjicad", max_posts: int = 1) -> Dict[str, Any]:
    """
    Complete Universal Workflow for ANY CIC Product:
    Keyword -> Find Hottest Posts -> Crawl Comments -> Qwen Sales Agent (with DB knowledge) -> Supabase
    """
    from keyword_search_engine import find_hottest_posts
    from facebook_comment_crawler import crawl_facebook_post_and_all_comments

    # 1. Find hottest posts
    hottest = find_hottest_posts(keyword, top_k=max_posts)
    if not hottest:
        return {"success": False, "error": f"Không tìm thấy bài viết nào cho từ khóa '{keyword}'"}

    total_leads = []
    hot_posts_processed = []

    for post in hottest:
        # 2. Crawl comments
        post_url = post["url"]
        crawled = crawl_facebook_post_and_all_comments(post_url, manual_content=post["title"])
        post_info = crawled["post_info"]
        post_info["title"] = post["title"]
        post_info["reactions_count"] = post["reactions_count"]
        raw_comments = crawled["comments"]

        # 3. Run Qwen Sales Agent with matching product knowledge
        agent = QwenCustomerIntelligenceAgent(post_info, raw_comments, product_key=keyword)
        analysis = agent.analyze_and_pitch()

        # 4. Persist to DB
        saved_count = agent.persist_results(analysis)
        analysis["saved_leads_count"] = saved_count

        total_leads.extend(analysis["customers"])
        hot_posts_processed.append({
            "post_title": post["title"],
            "url": post["url"],
            "engagement_score": post["engagement_score"],
            "comments_crawled": len(raw_comments),
            "customers_found": len(analysis["customers"]),
            "hot_leads": analysis["statistics"]["hot_leads"]
        })

    # 5. Trigger Telegram alert for hot leads if any
    hot_count = sum(1 for l in total_leads if l["tier"] == "HOT")
    if hot_count > 0:
        try:
            from notification.notification_runner import run_notification_cycle
            run_notification_cycle(20)
        except Exception:
            pass

    return {
        "success": True,
        "keyword": keyword,
        "product_knowledge_used": get_product_knowledge(keyword).get("product_name"),
        "posts_scanned": len(hot_posts_processed),
        "hot_posts": hot_posts_processed,
        "total_leads_identified": len(total_leads),
        "hot_leads_count": hot_count,
        "leads": total_leads
    }'''

new_pipeline = '''def run_keyword_pipeline(keyword: str = "enjicad", max_posts: int = 5) -> Dict[str, Any]:
    """
    Complete Universal Workflow for ANY CIC Product:
    Keyword -> Find Hottest Posts -> Parallel Crawl Comments -> Qwen Sales Agent -> Supabase
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import threading
    from keyword_search_engine import find_hottest_posts
    from facebook_comment_crawler import crawl_facebook_post_and_all_comments

    # 1. Find hottest posts with user-chosen quantity
    hottest = find_hottest_posts(keyword, top_k=max_posts)
    if not hottest:
        return {"success": False, "error": f"Không tìm thấy bài viết nào cho từ khóa '{keyword}'"}

    total_leads = []
    hot_posts_processed = []

    def process_single_post(post):
        try:
            post_url = post["url"]
            crawled = crawl_facebook_post_and_all_comments(post_url, manual_content=post["title"])
            post_info = crawled["post_info"]
            post_info["title"] = post["title"]
            post_info["reactions_count"] = post["reactions_count"]
            raw_comments = crawled["comments"]

            agent = QwenCustomerIntelligenceAgent(post_info, raw_comments, product_key=keyword)
            analysis = agent.analyze_and_pitch()
            saved_count = agent.persist_results(analysis)
            analysis["saved_leads_count"] = saved_count

            summary = {
                "post_title": post["title"],
                "url": post["url"],
                "engagement_score": post["engagement_score"],
                "comments_crawled": len(raw_comments),
                "customers_found": len(analysis["customers"]),
                "hot_leads": analysis["statistics"]["hot_leads"]
            }
            return analysis["customers"], summary
        except Exception as e:
            return [], None

    workers = min(8, len(hottest))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(process_single_post, p) for p in hottest]
        for f in as_completed(futures):
            custs, summary = f.result()
            if summary:
                total_leads.extend(custs)
                hot_posts_processed.append(summary)

    # Trigger Telegram alert in background thread so API response is instant
    hot_count = sum(1 for l in total_leads if l.get("tier") == "HOT")
    if hot_count > 0:
        def bg_notify():
            try:
                from notification.notification_runner import run_notification_cycle
                run_notification_cycle(20)
            except Exception:
                pass
        threading.Thread(target=bg_notify, daemon=True).start()

    return {
        "success": True,
        "keyword": keyword,
        "product_knowledge_used": get_product_knowledge(keyword).get("product_name"),
        "posts_scanned": len(hot_posts_processed),
        "hot_posts": hot_posts_processed,
        "total_leads_identified": len(total_leads),
        "hot_leads_count": hot_count,
        "leads": total_leads
    }'''

if old_pipeline in text:
    text = text.replace(old_pipeline, new_pipeline)
    with open('/home/ADMIN/qwen_sales_agent.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print("Updated run_keyword_pipeline with parallel processing")
else:
    print("Old pipeline pattern not matched")
