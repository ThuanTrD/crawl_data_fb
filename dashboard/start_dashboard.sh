#!/bin/bash
python3 -c 'import subprocess, os, signal; [os.kill(int(p), signal.SIGTERM) for p in subprocess.run(["pgrep", "-f", "[a]pp.py"], capture_output=True, text=True).stdout.split() if int(p) != os.getpid()]' 2>/dev/null || true
sleep 1
export PYTHONPATH=/home/ADMIN:$PYTHONPATH
export DATABASE_URL='postgresql://postgres.qllwfecwujzhuwexrlqi:tRpWn0s3s8OxILhQ@aws-0-ap-southeast-2.pooler.supabase.com:5432/postgres'
PORT=5678
cd /home/ADMIN/dashboard
PORT=5678 nohup /usr/bin/python3 app.py > /home/ADMIN/dashboard/dashboard.log 2>&1 &
DASHBOARD_PID=$!
echo "Native Python Dashboard PID: $DASHBOARD_PID"
sleep 2
STATUS_CHECK=$(curl -s http://127.0.0.1:5678/api/stats | grep -o '"success":true' || echo "FAILED")
echo "API Stats Check: $STATUS_CHECK"
