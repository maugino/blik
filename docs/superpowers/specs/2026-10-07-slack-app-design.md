# Slack app: cycle creation and reminders in DMs

Date: 2026-10-07
Status: revision 2, proposed after design review; replaces revision 1

Revision 1 captured the product direction. This revision makes the request
lifecycle, authorization, billing, token ownership, and delivery outcomes
explicit. Its changed decisions are proposals for review, not previously
approved behavior. The privacy requirements below are fixed product
constraints, confirmed by the user, rather than optional design choices.

## Goal

Let a Blik organization connect its Slack workspace so that review cycles can
be created from Slack and every reviewer-facing message (invitation,
self-assessment, reminder, report ready, ready to close) lands as a Slack DM
instead of an email whenever the recipient is in that workspace and Slack
accepts delivery. Reviewers who are not in Slack keep getting email.

Hosted customers first. The integration lives inside the Django project so
self-hosted installs get it too by registering their own Slack app.

Out of scope for this spec: hardening the public API or webhooks so that a
third party could build the same thing externally. The API has no
reviewer-slot endpoint, webhooks deliver once with no retries, and the
`send_reminders` API action is broken. Those are separate work items.

## Fixed privacy requirements

Blik is a privacy-first reviewer tool. The Slack integration must preserve
existing access boundaries and minimize the review information it exposes.

- **Creating a cycle never grants access to someone else's report.**
  `created_by` is attribution, not authorization. No new permission, setting,
  notification, or bearer link may turn authorship into report access.
  Any access must come independently from the existing reviewee/authorized
  report-viewer policy and remain scoped to the current organization.
- **Check access at disclosure time.** Recheck active membership and current
  permissions before displaying status and before queuing, sending, or
  retrying a protected notification. Revocation suppresses pending delivery.
  Failed or ambiguous authorization discloses nothing; it is not a reason
  to fall back to email.
- **Keep Slack content minimal.** Notifications contain the information
  needed to take the permitted action, never response text, report scores,
  report breakdowns, or links between individual reviewers and answers.
  `/blik status` shows aggregate completion counts only for already-visible
  cycles, without reviewer identities or per-person completion status.
- **Keep report links within the existing access policy.** A reviewee's
  bearer report URL goes only to that reviewee through the existing delivery
  policy. Other independently authorized recipients receive an authenticated
  report URL. A creation receipt may confirm the action the caller took,
  but must not disclose subsequent feedback or protected report information.
- **Minimize stored and logged data.** Request/recovery records must not
  become a second store of review content or a reviewer-identity directory.
  Apply the retention, deletion, and log restrictions in this specification.

## Design decisions

| Decision | Choice |
|---|---|
| Where the code lives | Inside the Django monolith, new `slack` app. No separate service. |
| Slack client | Stdlib `urllib.request` and `hmac`. No `slack_sdk`, no `requests`. |
| Identity resolution | By email at request or send time. No reusable directory mapping Slack identities to Blik accounts. Short-lived request records retain the caller and selections only to process that request. |
| Workspace to org | One to one. |
| Cycle creation depth | Full modal in Slack, never leaves Slack. |
| Reminder cadence | Automatic reminders every 3 days, up to 3 per token by default; both org-adjustable. Confirmed manual reminders also count toward that automatic limit. |
| Channel choice | Prefer Slack; fall back to email only when Slack delivery is known not to have occurred. An uncertain send is surfaced for resolution, without automatic fallback. |
| Scheduler | Existing cron infrastructure. Daily reminder selection plus a one-minute recovery pass for pending work. No Celery or separate service. |
| Post-submit work | `transaction.on_commit` starts a daemon thread for prompt processing. Database request and delivery records make interrupted work discoverable and prevent duplicate effects. |
| Authorization | Fixed privacy constraint: creating a cycle never grants report access. Preserve current report visibility and enforce permissions on the server and at notification delivery. |

### Invariants and scope

1. Slack acknowledgement handlers perform no Slack API or SMTP calls.
2. One modal request creates at most one cycle and consumes at most one credit.
3. Every assigned reviewer, including the reviewee, receives the URL for
   their existing token. Successful delivery is recorded against that token.
4. Slack and browser entry points enforce the same creation, organization,
   and hosted entitlement rules.
5. Only a confirmed send advances invitation/reminder success fields.
   An uncertain send blocks automatic repeat delivery for that token.
6. Cycle creation grants no access to someone else's report; every disclosure
   requires independent, current authorization.

The new request record and notification delivery record are deliberate
additions to revision 1. They cover billable creation, duplicate callbacks,
and ambiguous network outcomes; they are not a general-purpose task queue.
The existing best-effort webhook subsystem remains outside this change.

A staged modal is preferred over doing lookups synchronously or moving
creation to a web form: it preserves the full Slack flow without depending
on lookup latency. A database record plus threads and cron provides recovery
within the current deployment, without introducing a worker service.

## Part 1: Slack app registration and install

### The Slack app itself

Blik owns a production Slack app, registered in Blik's own workspace,
with **Public Distribution** enabled under
Manage Distribution. Public distribution is not a Marketplace listing. It only
means any workspace may install via OAuth using Blik's client id and secret.
The app is not discoverable; installs happen from Blik's "Connect Slack"
button.

Two apps are registered: production, with request URLs on the hosted domain,
and development, with request URLs on a local tunnel. They are configured
identically otherwise.

Credentials come from env and are read in `blik/settings.py`:

```
SLACK_CLIENT_ID
SLACK_CLIENT_SECRET
SLACK_SIGNING_SECRET
```

When `SLACK_CLIENT_ID` is empty the "Connect Slack" button is hidden and
every other code path behaves as if no workspace is connected.
Slack HTTP endpoints reject requests when any required credential is
missing; never verify a signature using an empty signing secret.

Self-hosters register their own app from `docs/slack-manifest.yaml`, swap in
their domain, and set the same three env vars. They do not need public
distribution because they install into one workspace.

**Bot scopes:** `commands`, `chat:write`, `users:read`, `users:read.email`,
`im:write`. No channel or message reading scopes.

**Request URLs** (all under `/slack/`):

| Path | Who calls it | Purpose |
|---|---|---|
| `install/` | Org admin (browser) | Redirect to Slack's authorize page |
| `oauth/callback/` | Slack redirects admin's browser | Exchange code, store workspace |
| `commands/` | Slack | The `/blik` slash command |
| `interactions/` | Slack | Modal submissions |
| `disconnect/` | Org admin (browser, POST) | Revoke and remove the connection |

No Events API subscription, so no events endpoint.

### Install flow

1. An admin with `accounts.can_manage_organization` clicks "Connect Slack" on
   the organization settings page (`settings_view` in `blik/admin_views.py`,
   template `templates/admin_dashboard/settings.html`).
2. `install/` builds a signed, ten-minute state containing the org, user,
   and a random nonce stored in that user's session. It redirects to
   `https://slack.com/oauth/v2/authorize` with
   the client id, the bot scopes, the redirect URI, and the state.
3. `oauth/callback/` verifies `state` with `signing.loads(max_age=600)`,
   checks the session nonce, exact logged-in user and organization, and
   rechecks `accounts.can_manage_organization`. Consume the nonce once.
   It exchanges `code` at `oauth.v2.access` and writes a `SlackWorkspace` row. An existing row for
   the org is replaced (reinstall). Redirects back to settings with a success
   message.
4. "Disconnect" is CSRF-protected and requires the same admin permission.
   It calls `auth.revoke` with the bot token (best effort, log failures)
   and deletes the row. Cancel outstanding uncommitted Slack creation
   requests. Already-created cycles and delivery audit records remain.

Check workspace uniqueness in a transaction and handle the database
constraint race with the same settings-page error as a pre-check conflict.
An unsuccessful reinstall must leave the previous connection usable.

### Model

```python
class SlackWorkspace(TimeStampedModel):
    organization = OneToOneField(Organization, on_delete=CASCADE, related_name='slack_workspace')
    team_id = CharField(max_length=32, unique=True)
    team_name = CharField(max_length=255)
    bot_user_id = CharField(max_length=32)
    bot_token_encrypted = BinaryField()          # Fernet, same key and scheme as Organization.smtp_password
    installed_by = ForeignKey(User, null=True, on_delete=SET_NULL)
    is_active = BooleanField(default=True)
```

`bot_token` is a property with a setter, mirroring `Organization.smtp_password`.
`team_id` is unique so one workspace cannot be connected to two orgs.

### Request verification

Every request to `commands/` and `interactions/` is verified before parsing:

```python
sig_basestring = b"v0:" + timestamp.encode("ascii") + b":" + request.body
expected = "v0=" + hmac.new(
    settings.SLACK_SIGNING_SECRET.encode(), sig_basestring, hashlib.sha256
).hexdigest()
```

Here `timestamp` is the validated timestamp header string. Sign the original
body bytes before decoding form data or JSON.
Reject with 401 when the timestamp is more than 300 seconds from now or
`hmac.compare_digest(expected, X-Slack-Signature)` is false. Both views are
`csrf_exempt`; the signature is the CSRF defence.

### Resolving people

Two directions, both by email, without a persistent identity directory.

**Blik to Slack.** `users.lookupByEmail` with the email already on the
`ReviewerToken`, `Reviewee`, or `User`. A hit that is not deleted and not a
bot yields a user id for the DM. Anything else (not found, deactivated,
guest without email, API error) means fall back to email. The Slack user id
is used for the one `chat.postMessage` call and discarded.

**Slack to Blik.** A slash command or modal payload carries the caller's
Slack `user_id`. `users.info` yields `profile.email`. Match case-insensitively
to exactly one active `User` whose `UserProfile.organization` is the active
workspace's organization. Reject missing, inactive, or ambiguous matches;
do not use `.first()` to choose between duplicate accounts. The caller must
also be an active, non-bot Slack member. Resolve in background work, not in
the acknowledgement handler. Explain failures in the loading modal or an
ephemeral command response without exposing another organization's data.

### Authorization and hosted entitlement

Use a shared creation policy from `reviews/services.py`, called by Slack
and the browser `review_cycle_create` POST:

- The actor is active and belongs to the workspace/request organization.
- The questionnaire belongs to that organization; a displayed option is
  not sufficient validation of the submitted identifier.
- If `profile.can_create_cycles_for_others` is false, the normalized
  reviewee email must equal the actor's email. Hiding a UI choice is not an
  authorization check.
- Slack may automatically create a missing reviewee for an organization
  admin, or for the actor's own email. A non-admin allowed to create cycles
  for others can select existing reviewees but cannot create new profiles
  for them. Reactivation requires organization admin permission, matching
  the existing profile-edit restriction.
- Before adding or reactivating a reviewee, call `check_employee_limit`.
  Reusing an already-active reviewee does not consume an employee slot.
  Refuse lapsed hosted subscriptions before cycle creation. Preserve the
  existing self-hosted and purchased-credit entitlement modes.
- Keep credit consumption in `ReviewCycle.save()`. Do not charge a second
  time in the Slack handler. Reviewee changes, cycle, tokens, and the
  successful request result commit or roll back together.

Serialize active-reviewee additions per organization while checking its
limit, and use that same guarded path for browser additions/reactivations.
On PostgreSQL use a row lock; the supported SQLite path must serialize writes
and handle lock conflicts without partially creating a profile or cycle.
Do not hold these transactions open while calling Slack or sending email.

For `/blik status`, scope by organization and then use `visible_cycles` and
`can_view_all_reports` from `accounts.permissions`, including its admin
compatibility rule. Do not substitute `created_by` for visibility. Recheck
permissions and membership before both queuing and sending report/close
notifications, including retries. Suppress the entire notification when
authorization fails, rather than merely removing its link.

**Privacy.** Review tokens already carry invitation email addresses and
responses reference those tokens. Slack DMs add a copy of a bearer link to
Slack, and temporary request data contains selected Slack identities. This
does not strengthen anonymity. Do not log bearer URLs, message bodies, raw
interaction payloads, response URLs, or bot tokens. Clear request inputs and
Slack user IDs after success or expiry, as described below.

## Part 2: Cycle creation in Slack

### Slash command

`/blik` with no text, or `/blik new`, acknowledges immediately after signature
verification and workspace lookup. Start an immediate thread whose first
Slack call is `views.open` with a loading view and the command's `trigger_id`.
Do not resolve the caller or load questionnaires before opening that view.
The loading view contains no organization data and has no submit button.

Slack requires acknowledgement within three seconds; a modal trigger also
expires after three seconds. Target acknowledgement within one second and
start `views.open` immediately with a two-second transport timeout and no
retry using an expired trigger. If opening fails, use the command's ephemeral
`response_url` to explain that the user should run `/blik new` again. Do not
persist or log that URL. This deadline is an operational constraint, not a
guarantee that Slack will always respond in time.
[Slack modal lifecycle](https://docs.slack.dev/surfaces/modals/).

After opening, resolve and authorize the caller, create a `SlackCycleRequest`,
and use `views.update` to show the form. Put the request UUID, caller ID, and
form revision in signed, expiring `private_metadata`; bind the row to the
workspace, Slack caller, Blik actor, and Slack view ID. A failed authorization replaces
the loading view with an explanation and Close button.

`/blik status` acknowledges immediately, then resolves the actor and sends an
ephemeral response with visible active cycles: reviewee, questionnaire, and
aggregate completed/total assigned tokens; omit reviewer identities and
per-person completion status. Also show that actor's pending/failed Slack
creation receipts so an interrupted modal has a discoverable outcome,
without granting access to the cycle's later feedback or report.
Paginate or truncate with a dashboard link instead of exceeding Slack's
message limits. Unknown text gets a short usage line.

### The modal

| Block id | Element | Required | Resolves to |
|---|---|---|---|
| `reviewee` | `users_select` | yes | Slack user, resolved by the worker to an authorized existing/new reviewee; self-only actors see their own identity fixed instead |
| `questionnaire` | `static_select` | yes | Org's questionnaires, as the web create form lists them |
| `peers` | `multi_users_select` | no | One `peer` token per resolved email |
| `managers` | `multi_users_select` | no | One `manager` token per resolved email |
| `direct_reports` | `multi_users_select` | no | One `direct_report` token per resolved email |
| `external` | `plain_text_input`, multiline | no | Comma or newline separated emails, one `peer` token each |

One `self` token with the reviewee's email is always created.

Use `static_select` for up to 100 questionnaires. If there are none or more
than 100, show an explanatory view with a dashboard link; do not send an
invalid modal or silently omit choices. Supporting larger lists in Slack is
outside this version.

### Submission handling (`interactions/`, `type == view_submission`)

**Acknowledgement phase, with no network calls:**

1. Verify signature and payload type, active workspace, signed metadata,
   actor/view binding, and the current local account/permissions. Reject a
   stale form revision. The request row expires after 30 minutes.
2. Validate the payload shape, organization-scoped questionnaire, and external
   email syntax locally. Immediate field errors use Slack's
   `{"response_action": "errors", "errors": {block_id: message}}` response.
3. Atomically change the request from `draft`/`needs_input` to `pending`,
   persisting the submitted choices for this revision. A duplicate callback
   returns the stored pending/success result; it does not enqueue new work.
4. Return `response_action: update` with a processing view, no Create button,
   and a Check status action. Explain that closing the modal does not cancel
   accepted creation and that a confirmation will follow. Schedule processing
   through `on_commit`; the HTTP response must not wait for that work.

Use short database lock timeouts on this path. If the request cannot be
accepted promptly, return a retryable error without starting a worker.

**Worker phase:**

1. Claim the request atomically. Resolve each distinct selected Slack ID once
   with `users.info`, including the actor again before acting. Deactivated
   users, bots, or missing emails are validation failures for their field.
   Read calls may retry transient errors within a two-minute total processing
   budget; do not sleep indefinitely on rate limits.
2. Trim and lowercase emails. Deduplicate within categories and merge external
   addresses into peers. Drop the reviewee from all non-self categories.
   If one address remains in different reviewer categories, ask the user to
   choose one category rather than silently choosing or sending two tokens.
3. Recheck all creation and entitlement rules in Part 1. In one transaction,
   lock the request and organization, confirm the request is still current,
   reuse/create/reactivate the reviewee, create the cycle through its model
   credit gate, and create one assigned token per reviewer plus exactly one
   assigned self token. Match existing reviewee email case-insensitively;
   ambiguous existing records are an error, not a new profile.
4. In that transaction, save the cycle reference and successful request state
   and enqueue initial notification records. Any failure rolls back all
   profile, cycle, credit, and token changes. A successful request is terminal,
   including after a later cycle deletion: replay never recreates it.
5. Update the modal with a success view and Done button, or restore the form
   with the submitted values and labeled error text. A correction increments
   the form revision while keeping the same request UUID. Background errors
   cannot use the already-returned `response_action: errors` mechanism.
   Done is a new submission acknowledged with `response_action: clear`.
6. Send initial invitations using the exact assigned token IDs, including
   self, through `send_reviewer_invitations`. Do not additionally call the
   generic `send_reviewee_notifications` for Slack-created cycles. These
   cycles use assigned invitations; they do not send category sharing links.
   Send a creation confirmation with counts and delivery outcome, not an
   unconditional claim that everyone was invited. Include a detail link only
   if the creator is allowed to view that cycle.

The Check status action reads the durable result, so a closed view, failed
`views.update`, or race between acknowledgement and a fast worker never
changes the creation outcome. A late worker must match the request's current
revision and claim before writing any result.

### Duplicate requests and interrupted work

`SlackCycleRequest` contains a unique UUID, organization, nullable workspace
and actor references, view ID, temporary Slack caller ID and form inputs,
form revision, status, claim/lease timestamps, expiry, safe error codes, and
a nullable one-to-one cycle reference. Enforce uniqueness for a nonempty
workspace/view pair. State transitions and creation use the same row lock;
the unique request is the idempotency boundary, not an email or time window.

States are `draft`, `pending`, `processing`, `needs_input`, `succeeded`,
`failed`, and `expired`. Claim leases last five minutes; work exceeding its
two-minute budget fails without a partial commit. A recovery command can
claim pending requests and expired processing leases, but every worker must
prove it owns the current lease again inside the creation transaction.
An expired form or disconnected workspace cannot create a cycle.

Clear inputs and Slack user IDs when creation succeeds or a request expires.
Retain only the result/idempotency metadata for 30 days, then delete it.
The expired signed metadata prevents old callbacks from being accepted after
cleanup. Drafts need a new `/blik new` after expiry; recovery never invents a
new request on behalf of the user.

### Other interaction payloads

Dispatch by `type` and known callback/action IDs before applying form logic.
Verify and acknowledge URL-button `block_actions` without requiring a Blik
account: reviewers can use token links without one. Slack sends an interaction
even for a button that only opens a URL. Request-status buttons additionally
check their actor/workspace binding. Unsupported actions get a harmless
acknowledgement and no mutation.
[Slack button reference](https://docs.slack.dev/reference/block-kit/block-elements/button-element/).

## Part 3: Delivery and reminders

### `deliver`

A single function in `slack/client.py`:

```python
def deliver(delivery, *, subject, text, html, slack_text, slack_actions):
    """Return a recorded pending, sent, failed, or uncertain delivery outcome."""
```

Behaviour:

- No configured/active workspace, a lookup miss, or a lookup error before
  any send: use `core.email.send_email` with the same subject, text and HTML.
- Lookup hit: use `chat.postMessage` with fallback text, a section, and URL
  buttons. Escape interpolated names/questionnaire titles for Slack mrkdwn.
  Disable link/media unfurling for private feedback and report URLs.
- A successful API response, or email backend return value of one, confirms
  `sent`. Store the selected channel and confirmation time.
- A definite Slack rejection known to mean no message was created permits
  email fallback. Keep an explicit allowlist of such errors (for example
  invalid authentication or a denied recipient); rate limits are deferred
  with `Retry-After`, rather than busy-looping or silently changing channels.
- A timeout, connection loss after sending, ambiguous server error, or
  crash while a send is in flight becomes `uncertain`. Do not fall back,
  automatically resend, or count it as successful. Apply the same caution
  to an ambiguous SMTP failure. Unknown error classes default to uncertain.
- Known failure of both channels returns `failed`. Existing service callers
  receive structured errors, not a success-shaped channel string; exceptions
  cannot be swallowed and followed by a success timestamp/count update.

This promises no automatic cross-channel fallback after a possibly delivered
message; it does not promise exactly-once delivery by external providers.
Slack explicitly documents server errors where an operation may have partly
succeeded. An authorized admin may explicitly resend an uncertain delivery
after seeing the duplicate-delivery risk; that is a new audited attempt.
[Slack message errors](https://docs.slack.dev/reference/methods/chat.postMessage/).

### Delivery records and token ownership

Use `reviews.NotificationDelivery` for all channels, including installations
with no Slack credentials. It stores organization/cycle, optional reviewer
token, notification kind, normalized recipient email, unique logical delivery
key, channel, status (`pending`, `sending`, `sent`, `failed`, `uncertain`,
`superseded`), attempt/claim timestamps, next retry time, and a safe error code.
Render content at send time; do not persist bearer URLs or message bodies.

Initial invitation keys are stable per token. Close-check and initial
report-ready keys are stable per cycle/report and recipient. Reminder keys
identify a reserved reminder operation; explicit resends get a new operation
ID. Deduplicate identical recipient/event pairs, including creator=reviewee.
Do not enqueue a new initial invitation for a token whose historical
`invitation_sent_at` is already set; an explicit resend is a distinct action.
Keep records while the parent cycle exists, with organization/cycle deletion
cascading through them; include them in the existing personal-data deletion
and export paths.

Claim a record atomically before network work, and never hold its transaction
open during delivery. Multiple threads/cron processes cannot claim the same
record. Recover `pending` work automatically. A `sending` record with no result
after one minute is uncertain, not automatically retried: the process may
have died after sending. Keep each delivery attempt below that time budget.
Retry known non-delivery transient failures at most three times, honoring
`Retry-After`; then expose a failed result. Recheck cycle/token eligibility
before each send and supersede pending invitations/reminders for completed
tokens or closed cycles.

On confirmed delivery, update the record and token success fields in one
database transaction, conditional on the current claim and an unapplied
result. Duplicate completion callbacks cannot increment a count twice.
If delivery succeeded but that transaction fails, the
record remains uncertain on recovery; do not send again automatically. This
is the unavoidable boundary between a database and a remote messaging API.

For an assigned self token, the URL is `/feedback/{token.token}/`, exactly
like every other assigned invitation. Mark `invitation_sent_at` on that
token after successful delivery. `send_reviewee_notifications` must choose
this direct-token path whenever an assigned self token exists, and skip an
already-sent initial invitation. Only cycles without one use the existing
category claim link. Do not create or claim a second self token as part of
sending a notification.

All of these paths use the delivery record and shared routing service:

| Function | Slack button |
|---|---|
| `send_reviewer_invitations` (reviewer and self branches) | "Give feedback" / "Start self-assessment" |
| `send_reminder_emails` | "Give feedback" |
| `send_reviewee_notifications` self-assessment part | "Start self-assessment" |
| `send_reviewee_notifications` category-sharing part, for existing web flows | Three category link buttons |
| `send_close_check_emails` | "View cycle" |
| `reports.services.send_report_ready_notification` | "View report" |
| `blik.admin_views.send_individual_reminder` | Delegate to `send_reminder_emails(cycle, token_ids=[id], source='manual')` |

The bulk browser reminder action uses that same reminder service. Preserve
the existing email templates; do not leave direct `EmailMultiAlternatives`
sending in the individual-reminder view. Make the distinction between
`token_ids=None` (all eligible) and `token_ids=[]` (none) explicit.

The `slack_text` for each is a two or three line mrkdwn rendering of the
same information the email carries. No new templates; the text is built in
`slack/blocks.py`.

### Other DMs

- **Report ready.** In the existing `report_generated` signal in
  `api/signals.py`, enqueue within the report transaction and dispatch after
  commit a notification for the cycle creator only if they are still an
  active member of the same organization and independently authorized to
  view that report under the existing policy. Being its creator plays no
  part in the access decision. Recheck at actual delivery and on every retry.
  Use the authenticated report URL for an authorized creator; never
  grant report access by sending a reviewee bearer token to an otherwise
  unauthorized creator. Deduplicate signal repeats and report regeneration
  for the initial notification. When
  `Organization.auto_send_report_email` is true the reviewee is notified
  through the existing report email path, which gains a `deliver` call like
  the others. If creator and reviewee are the same person, honor that setting
  for automatic report delivery and send at most one notification.
- **Ready to close.** Keep the seven-day, at-least-one-response rule. Notify
  the reviewee and any creator currently authorized to access/close the
  cycle, deduplicating the same email. Track each recipient independently so
  one failed send does not repeat a successful send to someone else.
  `close_check_sent_at` records that the cycle's notification batch was
  scheduled; per-recipient delivery records determine its outcome and retries.
  Migrate historical non-null timestamps as already handled, without a
  retroactive creator notification.
- **Creation confirmation.** Part 2, worker step 6. Its delivery record becomes
  eligible once initial invitations have terminal outcomes, so the summary
  distinguishes sent, failed, and uncertain delivery. It may omit protected
  links without hiding the fact that creation succeeded.

No per-submission notifications to the creator. `/blik status` covers
progress on demand.

### Reminder scheduler

New management command `send_reviewer_reminders` in
`slack/management/commands/`. A token is **due** when all of these hold:

1. `reviewer_email` is set
2. `invitation_sent_at` is set
3. `completed_at` is null
4. `cycle.status == 'active'`
5. `reminder_count < organization.reminder_max`
6. `coalesce(last_reminder_sent_at, invitation_sent_at) <= now - organization.reminder_interval_days`
7. No pending, sending, failed, or unresolved uncertain invitation/reminder delivery
   exists for this token

Due tokens are grouped by cycle and passed to `send_reminder_emails(cycle,
token_ids=[...], source='automatic')`. It rechecks eligibility and reserves
the next delivery under a token lock; the query alone is not concurrency
protection. After confirmed sending, increment `reminder_count` and update
`last_reminder_sent_at` once. A failed/uncertain attempt changes neither.
An explicit admin resend can supersede a failed or uncertain record; no
automatic process resolves it by guessing or starts a fresh daily retry
sequence after the three permitted attempts have failed.

Manual individual and bulk reminders share eligibility, routing, reservation,
and accounting. They may override the automatic interval/maximum when an
authorized user explicitly requests them; those confirmed sends still count
toward subsequent automatic reminders. `reminder_max=0` disables automation,
not a deliberate manual send. Document this beside the settings inputs.
`--dry-run` reports due counts/IDs without creating delivery rows or sending.

Keep cron setup in `docker-entrypoint.sh`, with separately logged jobs:

| Schedule (UTC) | Management command |
|---|---|
| Daily at 09:00 | `send_cycle_reminders` |
| Daily at 09:00 | `send_reviewer_reminders` |
| Every minute | `process_slack_work` |

Each uses the existing environment-loading convention and redirects both
output streams to `/var/log/cron.log`. The environment allowlist gains `SLACK_`. One failed
daily job must not prevent the other running.

`process_slack_work` recovers creation requests, dispatches pending delivery
records (including email-only records), expires abandoned requests, and
flags stale in-flight sends for review. It uses the same claim functions as
threads; overlapping processes and multiple app containers must be safe.
It does not select new daily reminders or blindly retry uncertain sends.

**Behaviour change for existing orgs.** Automatic email reminders do not
exist today. After this ships every org, Slack-connected or not, reminds
reviewers every 3 days up to 3 times. `reminder_max = 0` turns it off for an
org. This is intended.

Existing invitation timestamps remain unchanged. Seed `reminder_count` to
one where `last_reminder_sent_at` is already set, otherwise zero: historical
exact counts are unavailable. Thus the post-upgrade cap is based on known
history, not a claim about lifetime sends. Already-due tokens are eligible
on the first daily run. Announce this rollout behavior and the opt-out in
release/admin notes before enabling it on hosted production.

## Part 4: Schema, settings UI, files

### Migrations

- `slack` initial migration: `SlackWorkspace` and `SlackCycleRequest`, with
  request uniqueness, state, expiry, lease, and pending-work indexes.
- Next `core` migration: `Organization.reminder_interval_days` (positive
  small integer, default 3, minimum 1) and `Organization.reminder_max`
  (positive small integer, default 3, minimum 0). Validate in the form and
  database; both are bounded by the field's supported range.
- Next `reviews` migrations: `ReviewerToken.reminder_count` (nonnegative
  integer, default 0), `NotificationDelivery`, and the historical reminder
  count backfill described above. Add unique delivery keys and indexes for
  pending work and token/recipient/event lookups.

Choose migration dependencies from the repository at implementation time;
do not reuse migration numbers from this proposal.

### Settings page

`settings_view` and `templates/admin_dashboard/settings.html` gain:

- A "Slack" card. When `SLACK_CLIENT_ID` is set: either a "Connect Slack"
  button linking to `/slack/install/`, or the connected team name with a
  "Disconnect" POST button. Hidden entirely when the env var is empty.
- Two number inputs, "Automatic reminder interval (days)" and "Maximum
  automatic reminders", with the manual-counting and opt-out explanation.
  These are per-organization values. Preserve existing `env_managed_fields()`
  handling for other settings; no new reminder environment variables are
  introduced in this revision.

### Operational visibility

The existing cycle detail/invitations page shows pending, sent, failed, and
delivery-unknown counts and the affected recipients to users already allowed
to manage that cycle. Initial creation must not say "invitations sent" when
records are still pending. Failed delivery supports an explicit retry;
uncertain delivery requires an explicit resend with a duplicate-risk message.
Only organization admins can resolve uncertain deliveries. A retry rechecks
current recipient, organization, token completion, and cycle state.

Log request/delivery IDs, sanitized error codes, elapsed time, and channel;
do not log the sensitive values listed in Part 1. Recovery reports numbers
of expired requests, failed deliveries, and unknown deliveries for operators.

### Files

```
slack/
  __init__.py
  apps.py
  models.py                 SlackWorkspace, SlackCycleRequest
  client.py                 api_call, signature verification, identity lookups, deliver
  blocks.py                 loading/form/processing/result views, DM blocks, status text
  services.py               request transitions, processing, worker claims, recovery
  views.py                  install, oauth_callback, disconnect, commands, interactions
  urls.py
  migrations/0001_initial.py
  management/commands/send_reviewer_reminders.py
  management/commands/process_slack_work.py
  tests/
docs/slack-manifest.yaml    app manifest with placeholder domain
docs/ADMIN_GUIDE.md         new "Slack" section: hosted connect, self-hosted app creation, env vars
```

Touched: `blik/settings.py` (three env vars, `slack` in `INSTALLED_APPS`),
`blik/urls.py` (`path('slack/', include('slack.urls'))`), `blik/admin_views.py`
(settings, creation policy, and individual/bulk reminder views),
`templates/admin_dashboard/settings.html`, the cycle detail/invitations
templates (delivery outcomes and resend controls), `reviews/services.py`
(shared creation policy, token ownership, notification reservation/accounting),
`accounts/services.py` (guarded reviewee creation/reactivation shared with web),
`reports/services.py` (reviewee report delivery), `api/signals.py` (enqueue
report notifications), `core/models.py`, `reviews/models.py`, `core/gdpr.py`
(delivery data lifecycle), and `docker-entrypoint.sh`.

### `api_call`

Implement `api_call(token, method, *, timeout, **payload)` using stdlib
`urllib.request`. Make transport errors distinguishable from Slack's `ok:false`
responses, retaining HTTP status, safe error code, and `Retry-After`. Never
log the request authorization or body. Sending code, not a blanket exception
handler, classifies definite failure versus uncertain delivery.

Use form encoding for OAuth token exchange and email lookup; use supported
JSON requests for the other methods. Supply client credentials correctly for
OAuth instead of assuming it uses an existing bot token. Use a two-second
timeout for `views.open`, ten seconds for ordinary background requests,
and enforce the request worker's overall time budget. Do not automatically
retry message sends with an ambiguous result.

## Part 5: Error handling summary

| Situation | Behaviour |
|---|---|
| Bad or stale Slack signature | 401, body not parsed |
| Caller has no unique active Blik account in the org | Loading-view/ephemeral explanation, nothing created |
| Caller lacks permission or submitted another org's questionnaire | Reject before creation, retain no unauthorized data |
| Report/cycle visibility revoked before a queued notification or retry | Suppress the protected notification entirely; no Slack message or email fallback |
| No cycle credits, lapsed subscription, or employee cap exceeded | Restore form with explanation; profile/cycle/token/credit transaction rolled back |
| Selected user has no usable email, or appears in conflicting categories | Restore values and label the field to correct |
| Invalid external email syntax | Immediate field error on `external` |
| Duplicate submission or concurrent worker | Return stored result; at most one cycle, charge, and initial invitation batch |
| Slack modal opening/update fails | Explain failure if possible; persisted creation outcome remains authoritative |
| Lookup miss/error before sending, or definite Slack rejection | Email fallback when no message could have been delivered |
| Slack rate limit | Bounded deferred retry, honoring `Retry-After` |
| Ambiguous Slack/SMTP result or crash during send | Mark uncertain, show delivery unknown, no automatic resend/fallback |
| Creation thread dies before commit | Recovery reclaims the request; the creation transaction prevents partial effects |
| Notification thread dies | Recover pending records; stale in-flight records become uncertain |
| Tampered or expired OAuth `state` | 400, nothing stored |
| Workspace already connected to another org | Callback refuses with a settings-page error |

## Part 6: Testing

Tests must exercise handler, worker, and service boundaries; testing only an
already-resolved payload would miss the main integration risks. No broad
page smoke-test suite is required.

| Area | Acceptance criteria |
|---|---|
| Request verification | Valid signature passes; missing/bad signature, malformed timestamp, and timestamps beyond either side of the five-minute window fail before payload parsing. |
| Acknowledgement | Block fake Slack/SMTP transports and prove command/submission acknowledgements return without waiting. Verify opening is attempted before user lookups, with the short timeout. |
| Modal lifecycle | Slow lookups, rate limits, validation errors, corrected revisions, closed views, failed updates, and Check status all preserve the durable outcome. Expired forms cannot create cycles. |
| Duplicate creation | Repeated and concurrent callbacks/workers for one request create one cycle, spend one credit, and enqueue one initial batch. Test recovery after a commit with a lost acknowledgement, plus an expired worker lease. |
| Authorization | Inactive/ambiguous actors, wrong workspace/view/caller, foreign questionnaires, self-only actors selecting others, forbidden reactivation, and permission changes during processing are rejected. Web POST uses the same policy. |
| Entitlement | New/reactivated reviewees at the cap fail; existing active reviewees remain usable; simultaneous additions do not exceed the cap; lapsed subscriptions fail; self-hosted mode works; insufficient credits leave no new profile/cycle/tokens. |
| Assigned tokens | Exactly one token per normalized reviewer and one self token; within-category deduplication; cross-category conflict; reviewee removal from other categories. |
| Self-assessment regression | Follow the actual delivered URL and submit the assessment: the pre-created self token completes, no second self token appears, invitation time is set, and completing all assigned tokens closes the cycle. Cover Slack and email. |
| Channel outcomes | Slack success, missing workspace, disabled configuration, lookup miss/error, definite rejection, rate limit, and accepted-but-response-lost cases. Unknown delivery sends no email and changes no success fields. Email zero/exception is not recorded as success. |
| Delivery recovery | Pending work resumes after thread loss; concurrent claimants send once; crash after transport but before DB update becomes uncertain; exhausted known-failure retries do not restart the next day. |
| Reminder accounting | Each due condition and its boundary; manual individual/bulk actions route through the shared service; count changes once per confirmed send; automatic limits include confirmed manual history; dry-run has no writes or sends. |
| Privacy boundary | A creator who may create cycles for others but lacks report-viewing rights cannot list their protected results, receive report-ready notifications, or obtain report links. Setting `created_by` alone never changes authorization. Status exposes no reviewer identities, per-person completion, scores, or answers. |
| Notification visibility | Independently authorized recipient loses permission/membership after enqueue or before retry: no protected Slack message, email fallback, or bearer link. Creator=reviewee, auto-report setting disabled, repeated report signal, and partial close-check delivery do not leak links or duplicate recipients. |
| OAuth | Encrypted token round-trip; expired/tampered/replayed state; different user/session; permission revoked during installation; workspace uniqueness race; unsuccessful reinstall preserves the old connection; disconnect requires POST and CSRF. |
| Migration and privacy | Existing invitations are not resent, historical reminder counts are backfilled, old close checks are not replayed, request inputs expire, and deletion/export covers delivery records. |

Use transaction/concurrency tests on PostgreSQL for row-lock behavior and
the SQLite-supported path for write-conflict recovery. Do not claim concurrency
coverage from ordinary mocked unit tests alone.

Manual acceptance uses the development app in Blik's workspace: create a cycle
with self, an internal reviewer and an external email; complete the delivered
self link; exercise validation correction and a repeated submission; run both
reminder modes; check permitted/forbidden report recipients; simulate a lost
send response and recover a stopped worker. Verify actual Slack acknowledgements
meet the three-second limit, and confirm uncertain sends are visible without
a second-channel message.

Release readiness requires these acceptance checks, a dry run of existing
organizations' due reminders, and documentation of opt-out and recovery.
