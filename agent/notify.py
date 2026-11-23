"""Builds the daily email and sends it over SMTP (Gmail app password)."""
from __future__ import annotations

import html
import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from zoneinfo import ZoneInfo


def build_email(matches: list[dict], note: str, stats: dict) -> tuple[str, str, str]:
    today = datetime.now(ZoneInfo("Asia/Dubai")).strftime("%d %b %Y")
    subject = f"Job Agent – {len(matches)} new matches – {today}"

    text = [subject, ""]
    rows = []
    for i, j in enumerate(matches, 1):
        text += [f"{i}. {j['title']} — {j['company']} ({j['location'] or 'UAE'})",
                 f"   {j['url']}",
                 f"   Score {j['score']} · Experience asked: {j['experience_asked']} · Source: {j['site']}",
                 f"   Why: {j['why']}", ""]
        rows.append(
            f"<tr><td style='padding:6px 8px;vertical-align:top'><b>{i}</b></td>"
            f"<td style='padding:6px 8px'><a href='{html.escape(j['url'])}'><b>{html.escape(j['title'])}</b></a>"
            f" — {html.escape(j['company'])}<br><span style='color:#555'>{html.escape(j['location'] or 'UAE')}"
            f" · {html.escape(j['site'])} · experience: {html.escape(str(j['experience_asked']))}"
            f" · score {j['score']}</span><br>{html.escape(j['why'])}</td></tr>"
        )
    if note:
        text += [f"Draft cover note for #1 ({matches[0]['title']} — {matches[0]['company']}):", "", note, ""]
    footer = (f"Feeds read: {stats['loaded']} jobs · after rules: {stats['prefiltered']} · "
              f"new (not sent before): {stats['unseen']} · ranked by Claude: {stats['ranked']}")
    text.append(footer)

    note_html = (f"<h3>Draft cover note for #1</h3><p style='white-space:pre-wrap'>{html.escape(note)}</p>"
                 if note else "")
    body_html = (f"<div style='font-family:Arial,sans-serif;font-size:14px'><h2>{html.escape(subject)}</h2>"
                 f"<table>{''.join(rows)}</table>{note_html}"
                 f"<p style='color:#777;font-size:12px'>{html.escape(footer)}</p></div>")
    return subject, "\n".join(text), body_html


def send(subject: str, body_text: str, body_html: str) -> None:
    user, password = os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"]
    to = os.environ.get("EMAIL_TO", user)
    msg = MIMEMultipart("alternative")
    msg["Subject"], msg["From"], msg["To"] = subject, user, to
    msg.attach(MIMEText(body_text, "plain", "utf-8"))
    msg.attach(MIMEText(body_html, "html", "utf-8"))
    with smtplib.SMTP_SSL(os.environ.get("SMTP_HOST", "smtp.gmail.com"), 465) as smtp:
        smtp.login(user, password)
        smtp.sendmail(user, [to], msg.as_string())
