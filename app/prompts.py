"""Prompt LinkedIn post, diadaptasi dari workflow n8n di repo sumber.

Fokus: personal branding berbasis pengalaman kerja offline (executive/administrative
support, procurement & vendor coordination) supaya HR/recruiter melihat keahliannya
dan menghubunginya. Remote adalah hasil yang diinginkan, bukan topik post.
"""
import calendar

PILLARS = {
    "Monday": (
        "A specific lesson from everyday administrative or executive support work "
        "(scheduling conflicts, document follow-ups, prioritising requests). "
        "Format: short story -> what you changed -> one question for other assistants."
    ),
    "Tuesday": (
        "One practical, small tip an assistant actually uses (calendar blocking, email triage, "
        "filing, checklists, Google Workspace or Microsoft Office). "
        "Format: the tip in one line -> why it helps -> how you apply it -> invite readers to share theirs."
    ),
    "Wednesday": (
        "A grounded insight about procurement or vendor coordination basics "
        "(quotations, purchase requests, comparing suppliers, keeping records). "
        "Format: the common mistake -> the simple habit that prevents it -> question about their process."
    ),
    "Thursday": (
        "A real coordination moment from office-based support work: a request that arrived "
        "incomplete, an approval that needed chasing, a schedule clash, or a vendor follow-up. "
        "Format: the situation -> exactly what you did -> what it taught you about getting things "
        "done through other people -> one question for assistants who handle similar requests."
    ),
    "Friday": (
        "A reflection on professionalism, reliability or communication as a support professional. "
        "Format: an observation about trust in support roles -> how you practise it -> a question that invites peers to compare notes."
    ),
    "Saturday": (
        "A weekend reflection on one standard you keep at your desk (accuracy, follow-up, clean records). "
        "Format: one observation from your own work -> why it matters in support roles -> "
        "a question inviting peers to compare notes. No job-seeking pitch."
    ),
    "Sunday": (
        "A short personal reflection on consistency or growth in support work, based on something "
        "that actually happened at work. Format: one honest observation -> what you changed -> "
        "a reflective question for readers."
    ),
}


def build_prompt(profile_summary, at):
    weekday = calendar.day_name[at.weekday()]
    post_date = at.strftime("%Y-%m-%d")
    return """Write one LinkedIn post for today ({weekday}, {post_date}).

Author profile:
{profile}

Author situation (very important):
The author is an administrative / executive support professional in Indonesia with hands-on, office-based experience in executive support, procurement and vendor coordination. She has not held a remote role yet and must never suggest that she has. She wants a remote role at an international company, and her route is personal branding: HR managers and recruiters anywhere in the world who hire Executive Assistants, Administrative Assistants and Procurement / Vendor Coordinators should recognise a concrete, transferable skill in the post, open her profile, and reach out. Write as a working professional describing how she does the job, so the work itself proves her value. Remote work is the outcome she wants, not the subject of the post. Never state that she is job hunting or looking for a remote role, and never use location-specific references that only make sense inside Indonesia.

Audience:
Primary: HR managers, recruiters and hiring managers worldwide for Executive Assistant, Administrative Assistant and Procurement / Vendor Coordinator roles.
Secondary: other assistants and coordinators who will comment and share their experience.
Write in English that a reader in another country understands immediately, without local idioms or jargon.

What makes this audience stop scrolling:
A concrete moment where she owned something end to end, kept information accurate, made a busy person's next step easy, or wrote something so clear that no follow-up was needed. Those are the signals recruiters screen for. Show them through one specific example; do not label them as "skills" or list them.

Content pillar for today:
{pillar}

Structure that earns engagement:
- Line 1-2: a concrete, specific hook under 12 words that makes the right reader feel "that is my problem too" or "I want to read this". No generic motivation, no throat-clearing, no "In today's fast-paced world".
- Middle: one clear idea with a real example from daily assistant / procurement work (a task, a habit, a small decision). Use short paragraphs of 1-3 lines and white space so it is easy to read on a phone.
- Naturally include 2-3 niche keywords recruiters actually search for, e.g. executive support, calendar management, stakeholder coordination, procurement coordination, vendor management. No keyword stuffing.
- End: one easy, specific question that can be answered in a single sentence, ideally about the reader's own workflow or experience. Avoid "Thoughts?", "Agree?", and engagement bait like "comment YES".
- Optional final nudge to connect only if it feels natural.

Strict rules:
- English, first person, warm, humble but confident. Sound like a real person, not a brand.
- 120-180 words total. No markdown, no bullet symbols, no links.
- Do NOT invent numbers, metrics, company names, clients, results, certifications or success stories. Describe habits, practices, lessons and what she is learning instead.
- Do NOT claim remote work experience, international experience, team leadership or achievements that are not stated.
- Do NOT frame the post as a job search, an open-to-work announcement, or a request for advice about remote work. No "I'm preparing for my first remote role" style lines.
- No hype or buzzwords (avoid: game-changer, revolutionized, crushed it, 10x, synergy, thrilled to announce, "I'm excited to share").
- No emojis inside sentences; at most 1 emoji, optionally at the end of a line.
- 3-5 relevant hashtags on the last line (e.g. #ExecutiveAssistant #AdministrativeAssistant #Procurement #VendorManagement). Do not use #OpenToWork.
- Make every sentence earn its place. If a line adds no information or feeling, cut it.

Return only the post text.""".format(
        weekday=weekday,
        post_date=post_date,
        profile=profile_summary.strip(),
        pillar=PILLARS[weekday],
    )
