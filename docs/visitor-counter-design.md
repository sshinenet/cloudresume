# Visitor counter — design

Design for the serverless backend behind the visitor counter on
stevenshine.info. Covers Cloud Resume Challenge steps 7–11 (JavaScript,
database, API, Python, tests).

## Goal

Display a visit count on the landing page, backed by a serverless API, with
no server to maintain and no per-request cost beyond what AWS charges for a
handful of Lambda invocations.

## Architecture

```
browser (stevenshine.info)
   │
   │  fetch()  ── GET /count   read only
   │            └ POST /count  increment, then read
   ▼
API Gateway (HTTP API)  ── CORS locked to the two site origins
   │
   │  AWS_PROXY integration
   ▼
Lambda (Python 3.12)
   │
   │  UpdateItem (atomic ADD) / GetItem
   ▼
DynamoDB — single item, id = "count"
```

The API is reached directly at its `execute-api` URL. It is deliberately not
placed behind CloudFront or a custom domain: that adds a distribution
behaviour, cache rules, and another certificate for no benefit at this scale.

## Counting semantics

The counter increments **at most once per browser per calendar day**.

On load, `main.js` reads `stevenshine-last-visit` from `localStorage`:

- value is missing or is not today's date → `POST /count` (increments), then
  store today's date
- value is today's date → `GET /count` (no increment)

Deduplication is per browser only. Clearing site data, using a private
window, or visiting from another device counts again. This is intentional —
the alternative is server-side identity tracking (cookies, IP hashing), which
means storing personal data to make a decorative number slightly more
accurate. No cookies, no IP logging, no PII.

The client is trusted to say whether it has already been counted. That is
acceptable here: the worst case is an inflated or deflated count on a
personal site. It is not an access-control boundary.

## AWS resources

All names use the `stevenshine-` prefix. This is a hard requirement, not a
convention: the least-privilege deploy credential scopes DynamoDB tables,
Lambda functions, and IAM roles to that prefix, so a differently-named
resource cannot be created by the deploy user.

| Resource | Name | Notes |
|---|---|---|
| `aws_dynamodb_table` | `stevenshine-visitor-count` | `PAY_PER_REQUEST`, hash key `id` (S). One item. |
| `aws_iam_role` | `stevenshine-visitor-counter-role` | Trusts `lambda.amazonaws.com`. |
| inline role policy | — | `dynamodb:UpdateItem`/`GetItem` on that one table ARN; `logs:CreateLogGroup`/`CreateLogStream`/`PutLogEvents`. |
| `aws_lambda_function` | `stevenshine-visitor-counter` | Python 3.12, handler `handler.lambda_handler`, table name via `TABLE_NAME` env var. |
| `aws_apigatewayv2_api` | `stevenshine-visitor-counter-api` | `protocol_type = "HTTP"`, CORS allowing `GET`/`POST` from the two site origins only. |
| `aws_apigatewayv2_integration` | — | `AWS_PROXY`, payload format 2.0. |
| `aws_apigatewayv2_route` ×2 | `GET /count`, `POST /count` | Both to the same integration. |
| `aws_apigatewayv2_stage` | `$default` | `auto_deploy = true`. |
| `aws_lambda_permission` | — | Lets API Gateway invoke the function. |

These go in a new `backend.tf`, leaving `main.tf`'s frontend stack alone.

The `archive` provider is added to `required_providers` to zip the function
source.

The `aws` provider was bumped from **4.67.0** to **5.100.0**. The original
intent was to leave the 2023 pin alone, but 4.67.0 predates Python 3.11 and
3.12 entirely — its newest Python Lambda runtime is `python3.10`, and
`terraform validate` rejects anything later. Deploying a new function on a
runtime that old was the worse trade.

The bump caused exactly one change to existing infrastructure: CloudFront's
origin `domain_name` moved from `stevenshine-info-bucket.s3.amazonaws.com` to
`stevenshine-info-bucket.s3.us-east-1.amazonaws.com`, because provider 5.x
returns the true regional endpoint from `bucket_regional_domain_name`. Same
bucket, and the regional form is what AWS recommends alongside Origin Access
Control. It applied in place in about 45 seconds with no downtime; both
hostnames returned 200 immediately afterwards.

## API contract

Both routes return `200` with `{"count": <integer>}` and
`Content-Type: application/json`.

- `GET /count` — returns the current value. Returns `0` if the item does not
  exist yet; does not create it.
- `POST /count` — atomically increments by 1 and returns the new value.
  Creates the item at `1` on first call.

Increment uses a single `UpdateItem` with `ADD #v :one` and
`ReturnValues="UPDATED_NEW"`. This is atomic server-side — no read-then-write
race, and no need for conditional expressions or retries.

Any other method returns `405`. Unexpected errors return `500` with a generic
body; details go to CloudWatch Logs, not to the client.

## Frontend

- `index.html` — add a small element for the number, e.g.
  `<span id="visitor-count">` inside a line near the footer.
- `main.js` — currently a comment only. Implements the `localStorage` check,
  the `fetch` call, and rendering. On any network or API failure it leaves
  the element blank rather than showing an error; a broken counter must not
  visibly degrade the page.

### Deployment gotcha

The existing `aws_s3_object` resources specify `source` but no `etag`. Without
it Terraform does not detect changes to file **contents**, so editing
`main.js` or `index.html` would not redeploy them. Both resources need
`etag = filemd5(...)` added, or the counter ships to nobody.

## Tests

Two suites, both dependency-light and runnable offline.

**Frontend** — `npm test`, using Node's built-in test runner. There are **no
npm dependencies at all**: `counter.js` takes `fetch` and `storage` as
parameters instead of reaching for browser globals, so the logic is testable
without `jsdom` or a browser. `main.js` keeps only the DOM wiring, thin enough
not to need a test of its own. Covers: first visit POSTs, same-day revisit
GETs, a later day POSTs again, blocked storage still counts, and error
responses / unparseable bodies / non-numeric counts / network failures all
yield `null` rather than throwing.

Because `main.js` imports `counter.js`, the page loads it as an ES module
(`<script type="module">`).

**Backend** — `pytest` with `moto` mocking DynamoDB. No AWS calls, no
deployment required.

- `GET` on an empty table returns `0` and creates nothing
- `POST` creates the item and returns `1` on first call
- `POST` increments an existing value
- `GET` after `POST` reflects the incremented value without changing it
- unsupported method returns `405`

## Build sequence

1. `backend/handler.py` and its tests, driven by the tests — runs entirely
   locally, no AWS needed.
2. `backend.tf` with the DynamoDB table, role, Lambda, and API.
3. `terraform plan` review, then apply. Record the API endpoint output.
4. `main.js` and `index.html` against the real endpoint, plus the `etag` fix.
5. `terraform apply` to publish the frontend; verify the number renders and
   increments once per day.

## Out of scope

CI/CD (steps 14–15). Automating this requires moving Terraform state to a
remote backend first, since GitHub Actions cannot reach local state — that is
a separate piece of work with its own prerequisites.
