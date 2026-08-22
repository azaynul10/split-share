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
  schema.sql              12 tables, foreign keys, constraints and indexes
  seed.sql                demo data: users, listings, orders, reviews, groups
  make_password_hash.py   generates Django-compatible PBKDF2 hashes
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
