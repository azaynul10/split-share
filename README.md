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
  views_auth.py           register, login, logout
  views_browse.py         catalogue, search, filters, sorting, listing detail
  views_wishlist.py       saved listings
  views_coupons.py        promo code validation
  decorators.py           login_required_raw, anonymous_only
  context_processors.py   session user exposed to every template
  urls.py                 route table

split_share_core/         Django settings, root URL conf, WSGI and ASGI entry points
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
python manage.py runserver
```

Then open http://127.0.0.1:8000. The catalogue is at `/browse/`.

There are no Django migrations to run. The app owns no models, so the schema comes only from
`db/schema.sql`.

| Route | Page |
|---|---|
| `/browse/` | catalogue with search, filters, sorting and pagination |
| `/listing/<id>/` | listing detail, reviews and promo code box |
| `/wishlist/` | saved listings |
| `/register/`, `/login/`, `/logout/` | authentication |
| `/coupons/validate/` | JSON endpoint used by the promo code box |

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
