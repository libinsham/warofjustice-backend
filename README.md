# NEWSHUB — Django Backend

Everything in this package is **real, working Django code** — every endpoint
below was started with `runserver` and exercised live over HTTP during
development (not just written and assumed correct). A couple of real bugs
were caught and fixed that way.

## 1. Setup

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env            # then fill in real values
python manage.py migrate
python manage.py seed_roles     # creates super_admin/admin/author/reader + permissions

# create your first super admin
python manage.py shell -c "
from apps.accounts.models import User, Role
role = Role.objects.get(name='super_admin')
u = User.objects.create(email='admin@newshub.test', username='admin', role=role, status='active')
u.set_password('ChangeMe123!')
u.save()
"

python manage.py runserver
```

Uses SQLite out of the box so you can get moving immediately. Set
`DB_ENGINE=postgres` in `.env` (plus the `DB_*` vars) to point at real
Postgres for staging/production — no code changes needed either way.

API docs (Swagger UI, auto-generated from the actual code): `/api/v1/docs/`

## 2. What's implemented

**Apps** (matches your spec's `apps/` layout): `accounts`, `categories`,
`posts`, `media_lib`, `videos`, `comments`, `notifications`, `analytics`, `core`.

**Models:** User, Role, Permission, Profile, Category, Tag, Post,
PostRevision, PostApproval, Media, Video, Comment, Notification,
NewsletterSubscriber, SiteSettings, AuditLog — the exact list from your spec.

**Auth — JWT via SimpleJWT:**
- `POST /api/v1/auth/register/` — reader sign-up
- `POST /api/v1/auth/register-author/` — reporter sign-up, starts `pending`
- `POST /api/v1/auth/login/` — blocks `pending`/`suspended` accounts
- `POST /api/v1/auth/refresh/` — rotating, blacklisted refresh tokens
- `GET /api/v1/auth/me/`

**RBAC:** `super_admin` / `admin` (editor) / `author` / `reader`, plus a
fine-grained `Permission` model for anything finer than role alone.
`User.has_role()` / `has_permission()` back every permission check —
enforced server-side in DRF permission classes, never just hidden in a UI.

**Posts — the full workflow, verified live end-to-end:**

```
draft → submit → submitted → under_review → approve/publish → published
                                           → reject → rejected
                                           → request_changes → changes_requested → author edits → resubmit
```

- `GET /api/v1/posts/` , `/api/v1/posts/{slug}/` — public, published-only
- `/api/v1/dashboard/posts/` — author's own posts (or all, for admins); create/edit/submit
- `/api/v1/admin/posts/{id}/approve|reject|request-changes|publish|archive/` — Admin/Editor/Super Admin only

Confirmed by test: authors get a 403 hitting admin endpoints directly;
authors get a 403 editing a post that's under review; every transition is
recorded in `PostApproval` (workflow) and `AuditLog` (system-wide).

**Media (Cloudflare R2, direct upload — binary never touches Django):**
- `POST /api/v1/dashboard/media/presign/` — validates type/size, returns a signed PUT URL
- `POST /api/v1/dashboard/media/confirm/` — records metadata after the browser uploads directly to R2
- `/api/v1/admin/media/` — full library for Admin/Editor/Super Admin

**Video (Bunny Stream — API key never leaves the server):**
- `POST /api/v1/dashboard/videos/create-slot/` — creates a Bunny video + returns a TUS upload signature for the browser to upload directly to Bunny
- `POST /api/v1/webhooks/bunny/` — Bunny calls this when transcoding finishes; updates status/playback URL

**Comments:** public read (approved only) + create (starts `pending`);
`/api/v1/admin/comments/{id}/moderate/` for Admin/Editor/Super Admin.

**User management (Super Admin only):**
`/api/v1/super-admin/users/{id}/set-role/` and `/set-status/` — promote a
pending author, suspend an account, change roles. Every change logged to `AuditLog`.

**Site Settings (key-value store, Super Admin write / public read):**
- `GET /api/v1/settings/` — public, used to render logo/social links/SEO defaults
- `POST/PATCH/DELETE /api/v1/settings/{key}/` — Super Admin only, verified live (401 for anonymous writes)

**Password reset & auth security:**
- `POST /api/v1/auth/forgot-password/` — always returns a generic message
  (never reveals whether the email exists); sends a real email via
  Django's email system (console backend for dev, SMTP for production —
  see `.env.example`)
- `POST /api/v1/auth/reset-password/` — one-time-use token via Django's
  built-in token generator, verified live including rejecting reuse
- `POST /api/v1/auth/change-password/` — for logged-in users, verified
  live including wrong-current-password rejection
- **JWT refresh token lives in an httpOnly, Secure (in production),
  SameSite=Lax cookie** — never in the response body, never readable by
  JavaScript. `POST /api/v1/auth/login/` and `/register/` set it;
  `POST /api/v1/auth/refresh/` reads it (no body needed) and rotates it;
  `POST /api/v1/auth/logout/` blacklists it and clears the cookie. All
  verified live end-to-end, including that a request without the cookie
  is correctly rejected.

**Public video & gallery feeds:**
- `GET /api/v1/videos/`, `/api/v1/videos/{slug}/` — published posts with
  a video attached, nested video object (playback/thumbnail URLs)
- `GET /api/v1/gallery/` — published posts with a featured image

**Admin video library:**
- `GET /api/v1/admin/videos/` — full video library across all users, for
  the admin media library's Videos tab. Admin/Editor/Super Admin only,
  verified live including the 403 for an author.

**Analytics (Admin/Editor/Super Admin):**
- `GET /api/v1/admin/analytics/summary/` — total/published/pending posts,
  total authors, total views, total videos
- `GET /api/v1/admin/analytics/top-posts/?limit=10`
- `GET /api/v1/admin/analytics/category-breakdown/`
- `GET /api/v1/admin/analytics/publishing-trend/?days=30`

All aggregated from existing Post/User data rather than a separate
tracking model — see the "not yet built" note on per-visit analytics.

## 3. Environment variables

See `.env.example`. Nothing secret is hard-coded — Django secret key, DB
credentials, R2 keys, and the Bunny API key all come from `.env` and are
never sent to the frontend.

## 4. Running the test suite

```bash
pytest
```

35 tests covering auth (registration, login gating for pending/suspended
accounts, password change/reset), the full approval workflow (draft →
submit → approve/reject/changes-requested → published, plus every
permission boundary — an author can't approve their own post, can't edit
a post under review, can't touch another author's post), and RBAC
boundaries across categories, site settings, user management, admin
videos, and comment moderation. Every test here mirrors a check that was
originally done by hand with live curl commands during development —
this suite locks those same behaviors in against regressions.

Running it for the first time is also how a registration/refresh-token
inconsistency was caught: the register endpoints were still returning
the refresh token in the response body after the login endpoint was
switched to the httpOnly-cookie flow. Fixed and now covered by a test.

## 5. Not yet built

- XML sitemap / robots.txt (structured data is done on the frontend's article page)
- A dedicated per-visit analytics model (the current analytics endpoints
  aggregate from existing Post/User data — total views, publishing
  trends, category breakdowns — which is simpler and always consistent,
  but won't give you per-visitor traffic analytics; that would need a
  proper PageView model logging each request)
- CI wiring for the test suite (a GitHub Actions workflow running `pytest`
  on every push would be the natural next step)

## 6. Suggested next phase

The backend is functionally complete for a v1. The natural next step is
the Next.js frontend — home page, article/category/video pages, author
dashboard, and the custom admin panel — wired against these exact endpoints.
