import json, sys
d = json.load(sys.stdin)
r = d["data"]["agent_report"]
stats = r["statistics"]
print("Total Comments:", stats["total_comments_crawled"])
print("Total Customers:", stats["total_prospective_customers"])
print("HOT Leads:", stats["hot_leads_count"])
print("Conversion:", stats["conversion_readiness_score"])
print()
for i, c in enumerate(r["customers"]):
    print(str(i+1) + ". " + c["author_name"] + " | Score: " + str(c["score"]) + " (" + c["tier"] + ") | " + c["profile_url"])
