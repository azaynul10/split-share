# Sub-Share

A marketplace for sharing subscription slots. Sellers list open seats on plans they already
pay for, buyers purchase a single slot instead of a whole subscription, and both sides track
orders, groups and earnings in one place.

## Stack

| Layer | Choice |
|---|---|
| Database | MariaDB 10.4 / MySQL 8 (InnoDB, utf8mb4) |
| Backend | Django (routing and templates only) |
| Data access | Raw SQL through parameterised cursors, no ORM |
| Frontend | Server-rendered HTML, CSS, vanilla JavaScript |

## Repository layout

```
db/
  schema.sql              12 tables with primary keys, foreign keys and constraints
  seed.sql                demo data: users, listings, orders, reviews, groups
  verify.sql              integrity checks to run after a fresh import
  make_password_hash.py   generates Django-compatible PBKDF2 hashes

marketplace/
  db_utils.py             cursor helpers; every query in the project goes through here
  views/
    auth.py               register, login, logout
    browse.py             catalogue, search, filters, sorting, listing detail
    home.py               landing page
    orders.py             checkout, payment, order review
    wishlist.py           saved listings
    coupons.py            promo code endpoint; calls the coupon service over HTTP
    reviews.py            listing reviews
    notifications.py      in-app notifications
    seller.py             seller dashboard
    groups.py             sharing groups
  decorators.py           login_required_raw, anonymous_only
  context_processors.py   session user exposed to every template
  urls.py                 route table

coupon_service/           separate Flask process that owns promo-code validation
  app.py                  POST /validate, GET /health, GET /_fault (demo fault injection)
  validation.py           the three coupon gates, storage-agnostic

split_share_core/         Django settings, root URL conf, WSGI and ASGI entry points
  telemetry.py            OpenTelemetry setup shared by both processes; exporter chosen by env
templates/                base layout plus the auth and marketplace pages
manage.py                 Django entry point
requirements.txt          Python dependencies
```

## Database setup

The two SQL files are the single source of truth. `schema.sql` drops and rebuilds the
database, so it is safe to re-run at any time.

XAMPP on Windows:

```powershell
Get-Content db\schema.sql | & 'C:\xampp\mysql\bin\mysql.exe' -u root
Get-Content db\seed.sql   | & 'C:\xampp\mysql\bin\mysql.exe' -u root
```

MySQL or MariaDB already on PATH:

```bash
mysql -u root -p < db/schema.sql
mysql -u root -p < db/seed.sql
```

Verify the import:

```sql
USE split_share;
SELECT COUNT(*) FROM Listings;   -- 30
SELECT COUNT(*) FROM Orders;     -- 50
```

Note that `schema.sql` begins with `DROP DATABASE IF EXISTS split_share`. Re-running it wipes
everything, so run `seed.sql` again straight afterwards.

## Running the app

MySQL has to be listening before Django starts, otherwise the first request fails with
`OperationalError (2002)`. On XAMPP, start MySQL from the control panel first.

```powershell
pip install -r requirements.txt
python -m coupon_service          # terminal 1, listens on :8001
python manage.py runserver        # terminal 2, listens on :8000
```

Then open http://127.0.0.1:8000. The catalogue is at `/browse/`.

The coupon service is optional for everything except the promo code box on the listing
page. If it is not running, that box reports "We could not check that code right now" and
the endpoint returns 503; the rest of the site is unaffected. Checkout does its own coupon
check inside the order transaction and never calls the service.

There are no Django migrations to run. The app owns no models, so the schema comes only from
`db/schema.sql`.

| Route | Page |
|---|---|
| `/browse/` | catalogue with search, filters, sorting and pagination |
| `/listing/<id>/` | listing detail, reviews and promo code box |
| `/wishlist/` | saved listings |
| `/register/`, `/login/`, `/logout/` | authentication |
| `/coupons/validate/` | JSON endpoint used by the promo code box; proxies to the coupon service |

### Coupon service

`marketplace/views/coupons.py` reads the listing price locally, then posts the code and
subtotal to `COUPON_SERVICE_URL` (default `http://127.0.0.1:8001`) with a
`COUPON_SERVICE_TIMEOUT` of 2 seconds. Each way the call can fail maps to its own status,
and the failure is recorded on the request span:

| Coupon service state | `/coupons/validate/` returns |
|---|---|
| healthy | the service's own response, normally 200 |
| not running / unreachable | 503 |
| responding slower than the timeout | 504 |
| returning 5xx | 502 |

The service has a demo-only fault switch for exercising those paths without touching code:

```
http://127.0.0.1:8001/_fault?mode=slow     sleeps 5 s on every /validate (past the timeout)
http://127.0.0.1:8001/_fault?mode=error    raises inside /validate, returns 500
http://127.0.0.1:8001/_fault?mode=none     back to normal
http://127.0.0.1:8001/health               200 when its database answers, 503 otherwise
```

Stopping the process covers the third case. All three show up in traces as one trace that
starts at `POST coupons/validate/` in `split-share-web` and continues into
`split-share-coupons`, with `status = ERROR` on both sides of the boundary.

## Observability

Every request produces an OpenTelemetry trace: one server span named after the route
(`GET browse/`, `POST login/`) with one child span per SQL statement carrying the full
query text. Logged-in requests are tagged with `enduser.id` and `enduser.role`. Set-up lives
in `split_share_core/telemetry.py` and runs from `manage.py` and `wsgi.py`.

With no configuration, spans are printed to the `runserver` console one per line, prefixed
`[otel]`. To ship them to a backend instead, copy `.env.otel.example` to `.env.otel` (which
is gitignored) and paste the ingest token; `telemetry.py` reads it at startup. The first
line the server prints tells you which mode it is in:

```
[otel] exporting spans to https://njh16107.live.dynatrace.com/api/v2/otlp (auth header set)
```

The same variables can be set in the shell instead, and shell values take precedence over
the file. For a local collector use `http://localhost:4318` and omit the headers. Bluebox
tokens (`dt0s16.…`) use `Authorization=Bearer <token>`; classic Dynatrace API tokens
(`dt0c01.…`) use `Authorization=Api-Token <token>`. A literal space is fine.
`OTEL_SERVICE_NAME` overrides the default `split-share-web`; `OTEL_SDK_DISABLED=true`
switches tracing off entirely. `python tools/otel_selftest.py` sends a handful of real
request spans and prints the raw OTLP response, which is the quickest way to prove the
token and endpoint work.

## Demo accounts

All demo accounts share the password `demo1234`.

| Role | Email |
|---|---|
| Administrator | admin@subshare.com |
| Seller | rafiul@example.com |
| Buyer | zaynul@example.com |

Passwords are stored as PBKDF2-SHA256 hashes, never as plaintext. To generate a hash for a
new account:

```bash
python db/make_password_hash.py yourpassword
```

## Data model

Twelve tables:

`Users`, `Categories`, `Platforms`, `Listings`, `Coupons`, `Orders`, `OrderStatusHistory`,
`Reviews`, `SharedGroups`, `GroupMembers`, `Wishlist`, `Notifications`

Design decisions worth noting:

- **`Listings.available_slots` is stored, not recalculated.** Counting approved orders on
  every browse request would slow the listing page down. The checkout transaction
  decrements it instead.
- **`OrderStatusHistory` is append-only.** Order status is never silently overwritten, so
  every approval or rejection records who changed it, when, and why.
- **`GroupMembers` and `Wishlist` use composite primary keys.** The pair of columns is the
  key, which makes joining a group twice or saving the same listing twice impossible at the
  database level rather than in application code.
- **There is no payments table.** Payment is collected off-platform; the order row carries
  `payment_status` and `payment_ref` so the full transaction record still lives in the
  database.

## Payment flow

1. The buyer places an order. The row is created with `order_status = 'Pending'` and
   `payment_status = 'unpaid'`.
2. The buyer pays through the external payment form.
3. The buyer returns and submits the transaction ID, which is written to
   `Orders.payment_ref` and moves `payment_status` to `pending_verification`.
4. An administrator verifies the reference and approves the order, which writes an
   `OrderStatusHistory` row and a notification, and decrements `available_slots`.

## Contributing

`main` is protected, so nobody pushes to it directly. Every change arrives through a pull
request, including from collaborators with write access.

Start each piece of work from an up to date `main`:

```bash
git checkout main
git pull origin main
git checkout -b feature/seller-dashboard
```

Commit as you go, then push the branch and open a pull request:

```bash
git push -u origin feature/seller-dashboard
```

After the pull request is merged, return to `main` and pull before starting the next branch.

Two rules that keep the project consistent:

- **Every database call goes through `marketplace/db_utils.py`.** No Django ORM, no models,
  no raw cursors opened elsewhere.
- **User input is always passed as a `%s` parameter**, never formatted into the SQL string.
  Compare `db_utils.py` for the correct and incorrect forms.
