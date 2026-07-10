"""
Your Gazette — Email Scheduler
--------------------------------
Two jobs:
  1. Friday 6 pm ET  — Send each columnist an invitation to submit their column
  2. Sunday 6 am ET  — Generate the PDF and email it to the subscriber

Setup:
    1. Install dependencies:
       pip install resend apscheduler supabase

    2. Set your environment variables:
       export RESEND_API_KEY=re_your_key_here
       export SUPABASE_URL=https://your-project-id.supabase.co
       export SUPABASE_ANON_KEY=your-anon-key-here
       export SITE_URL=https://yourgazette.com

    3. Run:
       python scheduler.py

    4. Test without waiting for Friday/Sunday:
       python scheduler.py --test
"""

import os
import resend
import datetime
import base64
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from supabase import create_client

# ─────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────
RESEND_API_KEY  = os.environ.get("RESEND_API_KEY",   "re_RJtcXtvm_8fNptZpwYmmSgi5CNLpvaq65")
SUPABASE_URL    = os.environ.get("SUPABASE_URL",     "https://ccmhhimbiwppsunoakwd.supabase.co")
SUPABASE_KEY    = os.environ.get("SUPABASE_ANON_KEY","sb_publishable_OuUvPtPrt3KkNMvLKV1rJg_jvk905gT")
SITE_URL        = os.environ.get("SITE_URL",         "https://yourgazette.net")
FROM_ADDRESS    = "Your Gazette <hello@contact.yourgazette.net>"

resend.api_key  = RESEND_API_KEY
db              = create_client(SUPABASE_URL, SUPABASE_KEY)


# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────
def get_issue_date():
    today = datetime.date.today()
    if today.weekday() == 6:
        return today
    days_ahead = (6 - today.weekday()) % 7
    return today + datetime.timedelta(days=days_ahead)


def make_submission_link(subscriber_id, columnist_id):
    return f"{SITE_URL}/submit.html?s={subscriber_id}&c={columnist_id}"


# ─────────────────────────────────────────────
#  SEND ACCEPTANCE INVITATION
#  Called when a new columnist is added
# ─────────────────────────────────────────────
def send_acceptance_invitation(subscriber_id, columnist_id, columnist_email):
    """Send a one-time acceptance invitation to a new columnist."""
    accept_url = f"{SITE_URL}/accept.html?s={subscriber_id}&c={columnist_id}"

    # Get subscriber name
    result = db.table("subscribers").select("name").eq("id", subscriber_id).single().execute()
    if not result.data:
        print(f"  ✗ Could not find subscriber {subscriber_id}")
        return False

    subscriber_name = result.data["name"]

    text_body = f"""Hi,

{subscriber_name} has invited you to write a weekly column for their personal newspaper on Your Gazette.

Your Gazette is a weekly newspaper written entirely by friends and family — delivered every Sunday morning. It only takes a few minutes to write your column each week.

Accept or decline your invitation here:
{accept_url}

— Your Gazette
"""

    html_body = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8"/>
<style>
  body {{ background:#f7f4ee; font-family:Georgia,'Times New Roman',serif; color:#1a1714; margin:0; padding:0; }}
  .wrap {{ max-width:520px; margin:40px auto; padding:0 24px 48px; }}
  .masthead {{ text-align:center; border-bottom:3px double #1a1714; padding-bottom:14px; margin-bottom:32px; }}
  .masthead-eyebrow {{ font-family:'Courier New',monospace; font-size:10px; letter-spacing:.18em; text-transform:uppercase; color:#7a7063; margin-bottom:6px; }}
  .masthead-title {{ font-size:30px; font-weight:bold; margin:0; }}
  .body-text {{ font-size:16px; line-height:1.7; margin-bottom:24px; }}
  .what {{ background:#ede9df; border:1px solid #c8c0b0; padding:16px 20px; margin-bottom:28px; }}
  .what-label {{ font-family:'Courier New',monospace; font-size:10px; letter-spacing:.16em; text-transform:uppercase; color:#7a7063; margin-bottom:10px; }}
  .what ul {{ margin:0; padding-left:20px; }}
  .what li {{ font-size:14px; line-height:1.6; margin-bottom:4px; }}
  .cta-btn {{ display:block; background:#2b4a2f; color:#ffffff !important; text-decoration:none; text-align:center; font-family:'Courier New',monospace; font-size:12px; letter-spacing:.14em; text-transform:uppercase; padding:16px 24px; margin-bottom:12px; }}
  .footer {{ font-family:'Courier New',monospace; font-size:10px; letter-spacing:.1em; text-transform:uppercase; color:#7a7063; text-align:center; border-top:1px solid #c8c0b0; padding-top:16px; }}
</style>
</head>
<body>
<div class="wrap">
  <div class="masthead">
    <p class="masthead-eyebrow">You've been invited</p>
    <p class="masthead-title">Your Gazette</p>
  </div>
  <p class="body-text">
    <strong>{subscriber_name}</strong> has invited you to write a weekly column for their personal newspaper on Your Gazette.
  </p>
  <div class="what">
    <p class="what-label">What this means</p>
    <ul>
      <li>You'll receive an email each Friday to write a short column</li>
      <li>Your column appears in their personal Sunday newspaper</li>
      <li>Takes just a few minutes — write as much or as little as you like</li>
      <li>You can skip any week, no pressure</li>
    </ul>
  </div>
  <a class="cta-btn" href="{accept_url}">Accept invitation &rarr;</a>
  <p class="footer">Your Gazette &nbsp;&middot;&nbsp; A personal paper for people you love</p>
</div>
</body>
</html>"""

    try:
        resend.Emails.send({
            "from":    FROM_ADDRESS,
            "to":      columnist_email,
            "subject": f"{subscriber_name} invited you to write for their Gazette",
            "text":    text_body,
            "html":    html_body,
        })
        print(f"  ✓ Acceptance invitation sent to {columnist_email}")
        return True
    except Exception as e:
        print(f"  ✗ Failed to send invitation to {columnist_email}: {e}")
        return False


# ─────────────────────────────────────────────
#  JOB 1 — Friday 6 pm: Invite columnists
# ─────────────────────────────────────────────
def send_friday_invitations():
    print(f"\n[{datetime.datetime.now()}] Running Friday invitation job...")

    # Load all columnists across all subscribers
    col_result = db.table("columnists").select("id, email, subscriber_id, status").execute()
    if not col_result.data:
        print("  No columnists found.")
        return

    # Only invite accepted columnists
    # Deduplicate by email — each columnist only gets one invitation
    seen_emails = {}
    for c in col_result.data:
        if c.get("status") == "accepted" and c["email"] not in seen_emails:
            seen_emails[c["email"]] = c

    sent   = 0
    errors = 0

    for email, columnist in seen_emails.items():
        submit_url = make_submission_link(columnist["subscriber_id"], columnist["id"])

        text_body = f"""Hi,

Your Gazette goes out this Sunday morning.

Write your column here — it only takes a few minutes:
{submit_url}

Deadline: Sunday at 5 am ET.

— Your Gazette
"""

        html_body = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8"/>
<style>
  body {{ background:#f7f4ee; font-family:Georgia,'Times New Roman',serif; color:#1a1714; margin:0; padding:0; }}
  .wrap {{ max-width:520px; margin:40px auto; padding:0 24px 48px; }}
  .masthead {{ text-align:center; border-bottom:3px double #1a1714; padding-bottom:14px; margin-bottom:32px; }}
  .masthead-eyebrow {{ font-family:'Courier New',monospace; font-size:10px; letter-spacing:.18em; text-transform:uppercase; color:#7a7063; margin-bottom:6px; }}
  .masthead-title {{ font-size:30px; font-weight:bold; margin:0; }}
  .body-text {{ font-size:16px; line-height:1.7; margin-bottom:28px; }}
  .deadline {{ font-family:'Courier New',monospace; font-size:11px; letter-spacing:.12em; text-transform:uppercase; color:#7a7063; margin-bottom:28px; }}
  .cta-btn {{ display:block; background:#2b4a2f; color:#ffffff !important; text-decoration:none; text-align:center; font-family:'Courier New',monospace; font-size:12px; letter-spacing:.14em; text-transform:uppercase; padding:16px 24px; margin-bottom:32px; }}
  .footer {{ font-family:'Courier New',monospace; font-size:10px; letter-spacing:.1em; text-transform:uppercase; color:#7a7063; text-align:center; border-top:1px solid #c8c0b0; padding-top:16px; }}
</style>
</head>
<body>
<div class="wrap">
  <div class="masthead">
    <p class="masthead-eyebrow">Your column is due</p>
    <p class="masthead-title">Your Gazette</p>
  </div>
  <p class="body-text">
    <strong>Your Gazette</strong> goes out this Sunday morning.
    Write your column — it only takes a few minutes.
  </p>
  <p class="deadline">&#9200; Deadline: Sunday at 5 am ET</p>
  <a class="cta-btn" href="{submit_url}">Write my column &rarr;</a>
  <p class="footer">Your Gazette</p>
</div>
</body>
</html>"""

        try:
            resend.Emails.send({
                "from":    FROM_ADDRESS,
                "to":      columnist["email"],
                "subject": f"Your column is due this Sunday",
                "text":    text_body,
                "html":    html_body,
            })
            print(f"  ✓ Invited {columnist['email']}")
            sent += 1
        except Exception as e:
            print(f"  ✗ Failed to invite {columnist['email']}: {e}")
            errors += 1

    print(f"  Friday job complete — {sent} sent, {errors} errors.\n")


# ─────────────────────────────────────────────
#  JOB 2 — Sunday 6 am: Generate + send PDF
# ─────────────────────────────────────────────
def send_sunday_gazette():
    print(f"\n[{datetime.datetime.now()}] Running Sunday delivery job...")

    try:
        from generate_gazette import generate_gazette
    except ImportError:
        print("  ✗ Could not import generate_gazette.py — make sure it's in the same folder.")
        return

    issue_date = get_issue_date()
    result     = db.table("subscribers").select("id, name, email").execute()

    if not result.data:
        print("  No subscribers found.")
        return

    sent   = 0
    errors = 0

    for subscriber in result.data:
        try:
            # 1. Load this subscriber's columnists
            col_result = db.table("columnists") \
                .select("id, email") \
                .eq("subscriber_id", subscriber["id"]) \
                .eq("status", "accepted") \
                .execute()

            columnists = col_result.data or []

            # 2. Load submissions for this week by columnist_id
            #    One submission covers all Gazettes the columnist writes for
            columnist_ids = [c["id"] for c in columnists]
            sub_result = db.table("submissions") \
                .select("columnist_id, author_name, body") \
                .in_("columnist_id", columnist_ids) \
                .eq("issue_date", issue_date.isoformat()) \
                .execute()

            submissions = { s["columnist_id"]: s for s in (sub_result.data or []) }

            # 3. Build columns list for PDF generator
            columns = []
            for c in columnists:
                sub = submissions.get(c["id"])
                if sub:
                    columns.append({
                        "author":    sub["author_name"],
                        "submitted": True,
                        "text":      sub["body"],
                    })
                else:
                    columns.append({
                        "author":    c["email"],
                        "submitted": False,
                        "text":      None,
                    })

            # 4. Generate PDF
            gazette_data = {
                "subscriber_name": subscriber["name"],
                "issue_date":      issue_date,
                "columns":         columns,
            }
            pdf_path = f"/tmp/gazette_{subscriber['id']}_{issue_date}.pdf"
            generate_gazette(gazette_data, pdf_path)

            # 5. Send email with PDF attached
            with open(pdf_path, "rb") as f:
                pdf_b64 = base64.b64encode(f.read()).decode()

            filename   = f"{subscriber['name'].replace(' ', '_')}s_Gazette_{issue_date}.pdf"
            submitted  = sum(1 for c in columns if c["submitted"])
            total      = len(columns)

            text_body = (
                f"Hi {subscriber['name']},\n\n"
                f"This week's {subscriber['name']}'s Gazette is attached.\n"
                f"{submitted} of {total} columnists wrote this week.\n\n"
                f"— Your Gazette"
            )

            html_body = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8"/>
<style>
  body {{ background:#f7f4ee; font-family:Georgia,'Times New Roman',serif; color:#1a1714; margin:0; padding:0; }}
  .wrap {{ max-width:520px; margin:40px auto; padding:0 24px 48px; }}
  .masthead {{ text-align:center; border-bottom:3px double #1a1714; padding-bottom:14px; margin-bottom:32px; }}
  .masthead-eyebrow {{ font-family:'Courier New',monospace; font-size:10px; letter-spacing:.18em; text-transform:uppercase; color:#7a7063; margin-bottom:6px; }}
  .masthead-title {{ font-size:30px; font-weight:bold; margin:0; }}
  .body-text {{ font-size:16px; line-height:1.7; margin-bottom:24px; }}
  .meta {{ font-family:'Courier New',monospace; font-size:11px; letter-spacing:.12em; text-transform:uppercase; color:#7a7063; margin-bottom:24px; }}
  .footer {{ font-family:'Courier New',monospace; font-size:10px; letter-spacing:.1em; text-transform:uppercase; color:#7a7063; text-align:center; border-top:1px solid #c8c0b0; padding-top:16px; }}
</style>
</head>
<body>
<div class="wrap">
  <div class="masthead">
    <p class="masthead-eyebrow">This week's edition</p>
    <p class="masthead-title">{subscriber['name']}'s Gazette</p>
  </div>
  <p class="body-text">
    Hi {subscriber['name']},<br/><br/>
    This week's edition of <strong>{subscriber['name']}'s Gazette</strong> is attached.
  </p>
  <p class="meta">{submitted} of {total} columnists wrote this week</p>
  <p class="footer">Your Gazette &nbsp;&middot;&nbsp; Delivered every Sunday morning</p>
</div>
</body>
</html>"""

            resend.Emails.send({
                "from":    FROM_ADDRESS,
                "to":      subscriber["email"],
                "subject": f"This week's {subscriber['name']}'s Gazette",
                "text":    text_body,
                "html":    html_body,
                "attachments": [{
                    "filename":     filename,
                    "content":      pdf_b64,
                    "content_type": "application/pdf",
                }],
            })

            # 6. Record the issue in the database
            db.table("issues").insert({
                "subscriber_id":   subscriber["id"],
                "issue_date":      issue_date.isoformat(),
                "pdf_path":        pdf_path,
                "columnist_count": submitted,
            }).execute()

            print(f"  ✓ Delivered to {subscriber['name']} ({subscriber['email']})")
            sent += 1
            os.remove(pdf_path)

        except Exception as e:
            print(f"  ✗ Failed for {subscriber['name']}: {e}")
            errors += 1

    print(f"  Sunday job complete — {sent} delivered, {errors} errors.\n")


# ─────────────────────────────────────────────
#  API SERVER
#  Simple HTTP server so the dashboard can
#  trigger invitation emails immediately
# ─────────────────────────────────────────────
def run_api_server():
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import json
    import urllib.parse
    import threading

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            if self.path == '/invite':
                length = int(self.headers.get('Content-Length', 0))
                body   = json.loads(self.rfile.read(length))
                ok = send_acceptance_invitation(
                    body["subscriber_id"],
                    body["columnist_id"],
                    body["email"]
                )
                self.send_response(200 if ok else 500)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"ok": ok}).encode())
            else:
                self.send_response(404)
                self.end_headers()

        def do_OPTIONS(self):
            self.send_response(200)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')
            self.end_headers()

        def log_message(self, format, *args):
            pass  # suppress logs

    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), Handler)
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    print(f"  API server running on port {port}")


# ─────────────────────────────────────────────
#  SCHEDULER
# ─────────────────────────────────────────────
def run_scheduler():
    scheduler = BlockingScheduler(timezone="America/New_York")

    scheduler.add_job(
        send_friday_invitations,
        CronTrigger(day_of_week="fri", hour=18, minute=0),
        id="friday_invitations",
        name="Send Friday columnist invitations",
        replace_existing=True,
    )

    scheduler.add_job(
        send_sunday_gazette,
        CronTrigger(day_of_week="sun", hour=6, minute=0),
        id="sunday_delivery",
        name="Generate and deliver Sunday gazette",
        replace_existing=True,
    )

    run_api_server()
    print("=" * 50)
    print("  Your Gazette Scheduler Running")
    print("  Friday 6:00 pm ET — columnist invitations")
    print("  Sunday 6:00 am ET — gazette delivery")
    print("=" * 50)

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("\nScheduler stopped.")


# ─────────────────────────────────────────────
#  TEST MODE
# ─────────────────────────────────────────────
def run_test():
    print("=" * 50)
    print("  YOUR GAZETTE — TEST MODE")
    print("=" * 50)
    print()

    choice = input("Run which job?\n  1 — Friday invitation emails\n  2 — Sunday gazette delivery\n  3 — Both\n\nChoice: ").strip()

    if choice in ("1", "3"):
        send_friday_invitations()
    if choice in ("2", "3"):
        send_sunday_gazette()


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    if "--test" in sys.argv:
        run_test()
    else:
        run_scheduler()
