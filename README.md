# cloudresume

My résumé site, running on AWS as a static site with a serverless visitor
counter. Live at **[stevenshine.info](https://stevenshine.info)**.

Built for the [Cloud Resume Challenge](https://cloudresumechallenge.dev/docs/the-challenge/aws/).
Every AWS resource here is defined in Terraform — nothing was clicked together
in the console.

## Architecture

```
                    ┌──────────────────────────────┐
   visitor ────────▶│ CloudFront (HTTPS, ACM cert) │
                    └───────────────┬──────────────┘
                                    │ Origin Access Control
                                    ▼
                           ┌────────────────┐
                           │ S3 (private)   │  site assets
                           └────────────────┘

   browser ──▶ API Gateway (HTTP API) ──▶ Lambda (Python) ──▶ DynamoDB
```

The S3 bucket is private and has no website endpoint. CloudFront reaches it
through Origin Access Control, and a bucket policy allows reads only from this
distribution — so the site is served exclusively over HTTPS through CloudFront.
Route 53 alias records point both the apex and `www` at the distribution, with
a DNS-validated ACM certificate covering both.

The visitor counter is a separate path: the page calls an API Gateway HTTP API,
which proxies to a Python Lambda that reads and updates a single DynamoDB item.

## Visitor counter

`GET /count` returns the current total. `POST /count` increments it and returns
the new value using a single atomic DynamoDB `ADD` — no read-then-write race,
so concurrent visits can't overwrite each other.

A visit counts **at most once per browser per UTC day**. The page records the
date in `localStorage`; on a repeat visit the same day it issues a `GET`
instead of a `POST`. That means no cookies, no IP logging, and nothing personal
stored anywhere — the tradeoff being that clearing site data or switching
devices counts again. For a number on a résumé page, that's the right trade.

The Lambda's IAM role can reach exactly one DynamoDB table and its own log
group, nothing else. CORS on the API allows only this site's two origins.

If the API is unreachable the counter line stays hidden and the page renders
normally. A decorative number should never be able to break the page.

## Layout

```
main.tf              S3, CloudFront, ACM, Route 53, and the site objects
backend.tf           DynamoDB, Lambda, IAM role, API Gateway
variables.tf         domain names
index.html           the page
style/style.css      styling
main.js              browser wiring for the counter
counter.js           counter logic, isolated from browser globals for testing
backend/handler.py   the Lambda
backend/tests/       Python tests (pytest + moto)
tests/               JavaScript tests (Node's built-in runner)
docs/                design notes
```

## Tests

```bash
npm test                          # 11 frontend tests, no dependencies
cd backend && python -m pytest    # 6 backend tests
```

Neither suite touches AWS. The backend tests mock DynamoDB with `moto`; the
frontend tests inject `fetch` and storage as parameters, so `counter.js` runs
under plain Node with no browser or DOM library. There are no npm dependencies
at all — the frontend suite uses Node's built-in test runner.

## Deploying

Deploys run in GitHub Actions. Two path-filtered workflows — one for the
backend, one for the frontend — run their test suite and then apply Terraform.
Pull requests run tests only. Both share a concurrency group, since they apply
the same state.

Actions authenticates to AWS through GitHub's OIDC provider, assuming a role
whose trust policy is pinned to this repository's `production` environment.
No long-lived AWS credentials are stored in the repository. That environment
requires a manual approval before any deploy proceeds.

State lives in a versioned, encrypted S3 bucket and uses S3-native locking, so
no DynamoDB lock table is needed.

To run it by hand instead:

```bash
terraform init
terraform plan
terraform apply
```

Terraform manages the site files as S3 objects, so an `apply` publishes content
changes as well as infrastructure changes.

`.gitattributes` normalises line endings to LF. Terraform hashes the site files
with `filemd5()`, so a CRLF working tree on Windows and an LF checkout in CI
would otherwise re-upload identical content on every deploy. The Lambda zip
pins its file mode for the same reason.

## Status

Done: HTML, CSS, static site on S3, HTTPS, DNS, JavaScript counter, DynamoDB,
API, Python, tests, infrastructure as code, source control, and CI/CD for both
backend and frontend.

Not yet: the write-up.
