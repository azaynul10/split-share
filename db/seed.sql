-- =====================================================================
-- Sub-Share : demo data
-- Run this AFTER schema.sql.
--
-- Every demo account uses the password:  demo1234
-- (stored as a Django-compatible PBKDF2-SHA256 hash, never plaintext)
--
-- Data invariants held by this file:
--   * Listings.available_slots = total_slots - SUM(approved slots)
--   * Coupons.times_used       = number of orders referencing that coupon
--   * Reviews only exist where the reviewer has an approved order
--   * Group members are the seller plus buyers with approved orders
-- =====================================================================

USE split_share;

SET FOREIGN_KEY_CHECKS = 0;
TRUNCATE TABLE Notifications;
TRUNCATE TABLE Wishlist;
TRUNCATE TABLE GroupMembers;
TRUNCATE TABLE SharedGroups;
TRUNCATE TABLE Reviews;
TRUNCATE TABLE OrderStatusHistory;
TRUNCATE TABLE Orders;
TRUNCATE TABLE Coupons;
TRUNCATE TABLE Listings;
TRUNCATE TABLE Platforms;
TRUNCATE TABLE Categories;
TRUNCATE TABLE Users;
SET FOREIGN_KEY_CHECKS = 1;

-- ---------------------------------------------------------------------
-- Users : 1 admin, 5 sellers, 10 buyers
-- ---------------------------------------------------------------------
INSERT INTO Users (user_id, first_name, last_name, email, password_hash, phone, role, created_at) VALUES
(1,  'Site',    'Administrator', 'admin@subshare.com',    'pbkdf2_sha256$600000$sxk29fqp1mz7vbnd$+AOlAYNHlxkAbdEPNNUMQ+s9mCFOTFqbIHmadKXRZmA=', '01700000000', 'admin',  '2026-05-01 09:00:00'),
(2,  'Rafiul',  'Hasan',         'rafiul@example.com',    'pbkdf2_sha256$600000$sxk29fqp1mz7vbnd$+AOlAYNHlxkAbdEPNNUMQ+s9mCFOTFqbIHmadKXRZmA=', '01711111111', 'seller', '2026-05-03 11:20:00'),
(3,  'Sadia',   'Karim',         'sadia@example.com',     'pbkdf2_sha256$600000$sxk29fqp1mz7vbnd$+AOlAYNHlxkAbdEPNNUMQ+s9mCFOTFqbIHmadKXRZmA=', '01722222222', 'seller', '2026-05-06 15:45:00'),
(4,  'Imran',   'Chowdhury',     'imran@example.com',     'pbkdf2_sha256$600000$sxk29fqp1mz7vbnd$+AOlAYNHlxkAbdEPNNUMQ+s9mCFOTFqbIHmadKXRZmA=', '01733333333', 'seller', '2026-05-09 10:05:00'),
(5,  'Mahin',   'Rahman',        'mahin@example.com',     'pbkdf2_sha256$600000$sxk29fqp1mz7vbnd$+AOlAYNHlxkAbdEPNNUMQ+s9mCFOTFqbIHmadKXRZmA=', '01744444444', 'seller', '2026-05-12 18:30:00'),
(6,  'Nabila',  'Ahmed',         'nabila@example.com',    'pbkdf2_sha256$600000$sxk29fqp1mz7vbnd$+AOlAYNHlxkAbdEPNNUMQ+s9mCFOTFqbIHmadKXRZmA=', '01755555555', 'seller', '2026-05-15 12:10:00'),
(7,  'Zaynul',  'Abedin',        'zaynul@example.com',    'pbkdf2_sha256$600000$sxk29fqp1mz7vbnd$+AOlAYNHlxkAbdEPNNUMQ+s9mCFOTFqbIHmadKXRZmA=', '01766666666', 'buyer',  '2026-05-18 08:55:00'),
(8,  'Hamim',   'Islam',         'hamim@example.com',     'pbkdf2_sha256$600000$sxk29fqp1mz7vbnd$+AOlAYNHlxkAbdEPNNUMQ+s9mCFOTFqbIHmadKXRZmA=', '01777777777', 'buyer',  '2026-05-20 14:25:00'),
(9,  'Saim',    'Zahid',         'saim@example.com',      'pbkdf2_sha256$600000$sxk29fqp1mz7vbnd$+AOlAYNHlxkAbdEPNNUMQ+s9mCFOTFqbIHmadKXRZmA=', '01788888888', 'buyer',  '2026-05-22 16:40:00'),
(10, 'Tanvir',  'Ahmed',         'tanvir@example.com',    'pbkdf2_sha256$600000$sxk29fqp1mz7vbnd$+AOlAYNHlxkAbdEPNNUMQ+s9mCFOTFqbIHmadKXRZmA=', '01799999999', 'buyer',  '2026-05-25 09:15:00'),
(11, 'Nusrat',  'Jahan',         'nusrat@example.com',    'pbkdf2_sha256$600000$sxk29fqp1mz7vbnd$+AOlAYNHlxkAbdEPNNUMQ+s9mCFOTFqbIHmadKXRZmA=', '01811111111', 'buyer',  '2026-05-28 19:00:00'),
(12, 'Sabbir',  'Rahman',        'sabbir@example.com',    'pbkdf2_sha256$600000$sxk29fqp1mz7vbnd$+AOlAYNHlxkAbdEPNNUMQ+s9mCFOTFqbIHmadKXRZmA=', '01822222222', 'buyer',  '2026-06-01 11:35:00'),
(13, 'Mehedi',  'Hasan',         'mehedi@example.com',    'pbkdf2_sha256$600000$sxk29fqp1mz7vbnd$+AOlAYNHlxkAbdEPNNUMQ+s9mCFOTFqbIHmadKXRZmA=', '01833333333', 'buyer',  '2026-06-04 13:50:00'),
(14, 'Farhana', 'Akter',         'farhana@example.com',   'pbkdf2_sha256$600000$sxk29fqp1mz7vbnd$+AOlAYNHlxkAbdEPNNUMQ+s9mCFOTFqbIHmadKXRZmA=', '01844444444', 'buyer',  '2026-06-07 10:20:00'),
(15, 'Arif',    'Hossain',       'arif@example.com',      'pbkdf2_sha256$600000$sxk29fqp1mz7vbnd$+AOlAYNHlxkAbdEPNNUMQ+s9mCFOTFqbIHmadKXRZmA=', '01855555555', 'buyer',  '2026-06-10 17:05:00'),
(16, 'Sumaiya', 'Islam',         'sumaiya@example.com',   'pbkdf2_sha256$600000$sxk29fqp1mz7vbnd$+AOlAYNHlxkAbdEPNNUMQ+s9mCFOTFqbIHmadKXRZmA=', '01866666666', 'buyer',  '2026-06-13 20:30:00');

-- ---------------------------------------------------------------------
-- Categories : the filter pills on the browse page
-- ---------------------------------------------------------------------
INSERT INTO Categories (category_id, name, description) VALUES
(1, 'Streaming', 'Movies, series and live television services'),
(2, 'Music',     'Music and podcast streaming services'),
(3, 'Design',    'Creative and design software subscriptions'),
(4, 'AI Tools',  'AI assistants and productivity subscriptions'),
(5, 'Education', 'Online course and learning platforms');

-- ---------------------------------------------------------------------
-- Platforms : the actual services, each inside one category
-- ---------------------------------------------------------------------
INSERT INTO Platforms (platform_id, category_id, name, brand_color, website) VALUES
(1,  1, 'Netflix',                '#e50914', 'https://netflix.com'),
(2,  1, 'Amazon Prime Video',     '#00a8e1', 'https://primevideo.com'),
(3,  1, 'Disney+ Hotstar',        '#0f1e46', 'https://hotstar.com'),
(4,  1, 'YouTube Premium',        '#ff0000', 'https://youtube.com/premium'),
(5,  2, 'Spotify',                '#1db954', 'https://spotify.com'),
(6,  2, 'Apple Music',            '#fa243c', 'https://music.apple.com'),
(7,  3, 'Canva Pro',              '#00c4cc', 'https://canva.com'),
(8,  3, 'Adobe Creative Cloud',   '#ff2d55', 'https://adobe.com'),
(9,  3, 'Figma',                  '#a259ff', 'https://figma.com'),
(10, 4, 'ChatGPT Plus',           '#10a37f', 'https://chat.openai.com'),
(11, 4, 'Claude Pro',             '#d97757', 'https://claude.ai'),
(12, 5, 'Coursera Plus',          '#0056d2', 'https://coursera.org');

-- ---------------------------------------------------------------------
-- Listings : 30 offers across 5 sellers
-- available_slots is already reduced by every approved order below
-- ---------------------------------------------------------------------
INSERT INTO Listings (listing_id, seller_id, platform_id, plan_name, description, total_slots, available_slots, price_per_slot, billing_cycle, region, status, expires_on, created_at) VALUES
(1,  2, 1,  'Premium 4K UHD',        'Original family plan, 4 screens, Ultra HD. Renews on the 1st of every month.', 4, 1, 320.00,  'monthly',   'Bangladesh', 'active',  '2026-12-12', '2026-05-20 10:00:00'),
(2,  2, 5,  'Family Plan',           'Six individual accounts under one family subscription.',                        6, 3, 145.00,  'monthly',   'Bangladesh', 'active',  '2026-11-30', '2026-05-21 11:30:00'),
(3,  2, 7,  'Pro Teams',             'Full Canva Pro with brand kit and unlimited exports.',                          5, 2, 210.00,  'monthly',   'Global',     'active',  '2027-01-15', '2026-05-23 09:45:00'),
(4,  2, 8,  'All Apps',              'Complete Creative Cloud suite billed quarterly.',                               2, 1, 480.00,  'quarterly', 'Bangladesh', 'active',  '2026-10-20', '2026-05-25 14:10:00'),
(5,  2, 10, 'Plus Team',             'Priority access during peak hours. Currently paused by the seller.',            2, 0, 590.00,  'monthly',   'Global',     'paused',  '2026-09-30', '2026-05-27 16:20:00'),
(6,  2, 4,  'Family Premium',        'Ad-free video and background play for up to five members.',                     5, 3, 180.00,  'monthly',   'India',      'active',  '2026-12-01', '2026-05-29 08:00:00'),
(7,  3, 1,  'Standard HD',           'Two screens, Full HD, no Ultra HD.',                                            4, 3, 240.00,  'monthly',   'Bangladesh', 'active',  '2026-11-11', '2026-06-01 12:00:00'),
(8,  3, 5,  'Duo Plan',              'For two people living at the same address.',                                    2, 1, 110.00,  'monthly',   'Bangladesh', 'active',  '2026-10-05', '2026-06-02 13:25:00'),
(9,  3, 9,  'Professional',          'Unlimited files, shared libraries and dev mode.',                               4, 2, 260.00,  'monthly',   'Global',     'active',  '2027-02-01', '2026-06-04 10:40:00'),
(10, 3, 12, 'Plus Annual',           'Unlimited certificates, billed once a year.',                                   5, 4, 350.00,  'yearly',    'Global',     'active',  '2027-06-30', '2026-06-06 15:15:00'),
(11, 3, 2,  'Prime Household',       'Prime Video plus free delivery benefits.',                                      6, 3, 130.00,  'monthly',   'Bangladesh', 'active',  '2026-12-25', '2026-06-08 09:55:00'),
(12, 3, 11, 'Pro Seat',              'Five times the usage limit of the free plan.',                                  3, 3, 620.00,  'monthly',   'Global',     'active',  '2026-11-18', '2026-06-10 17:30:00'),
(13, 4, 3,  'Super Plan',            'Sports, movies and originals in Full HD.',                                      4, 2, 95.00,   'monthly',   'Bangladesh', 'active',  '2026-10-31', '2026-06-12 11:05:00'),
(14, 4, 6,  'Family Six',            'Up to six people, lossless audio included.',                                    6, 4, 125.00,  'monthly',   'Bangladesh', 'active',  '2026-12-15', '2026-06-14 14:45:00'),
(15, 4, 7,  'Pro Teams Annual',      'Annual Canva Pro seat, cheaper per month.',                                     5, 4, 1900.00, 'yearly',    'Global',     'active',  '2027-03-01', '2026-06-16 10:20:00'),
(16, 4, 1,  'Premium 4K Shared',     'Four Ultra HD screens, invite sent within an hour.',                            4, 1, 300.00,  'monthly',   'Bangladesh', 'active',  '2026-09-20', '2026-06-18 16:00:00'),
(17, 4, 10, 'Plus Individual',       'Single seat with faster response times.',                                       2, 1, 640.00,  'monthly',   'Global',     'active',  '2026-11-05', '2026-06-20 08:35:00'),
(18, 4, 12, 'Plus Monthly',          'Month-to-month access to the full catalogue.',                                  4, 4, 420.00,  'monthly',   'Global',     'active',  '2026-12-31', '2026-06-22 13:10:00'),
(19, 5, 5,  'Family Bundle',         'Family plan with parental controls enabled.',                                   6, 4, 150.00,  'monthly',   'Bangladesh', 'active',  '2026-11-22', '2026-06-24 09:30:00'),
(20, 5, 8,  'Photography Plan',      'Photoshop and Lightroom with 20GB storage.',                                    3, 2, 390.00,  'quarterly', 'Bangladesh', 'active',  '2027-01-10', '2026-06-26 15:50:00'),
(21, 5, 4,  'Premium Family',        'Ad-free viewing for the whole household.',                                      5, 4, 175.00,  'monthly',   'Bangladesh', 'active',  '2026-10-18', '2026-06-28 11:15:00'),
(22, 5, 9,  'Organization Seat',     'Org-level seat with shared design system.',                                     4, 4, 310.00,  'monthly',   'Global',     'active',  '2027-04-01', '2026-06-30 17:40:00'),
(23, 5, 2,  'Prime Video Only',      'Streaming access without the shopping benefits.',                               4, 2, 99.00,   'monthly',   'Bangladesh', 'active',  '2026-12-08', '2026-07-02 10:25:00'),
(24, 5, 11, 'Pro Annual',            'Yearly Claude Pro seat at a discounted rate.',                                  3, 3, 5800.00, 'yearly',    'Global',     'active',  '2027-05-20', '2026-07-04 14:05:00'),
(25, 6, 1,  'Premium Yearly',        'Twelve months of Ultra HD paid upfront.',                                       4, 3, 3400.00, 'yearly',    'Bangladesh', 'active',  '2027-07-01', '2026-07-06 09:00:00'),
(26, 6, 3,  'Mobile Plan',           'Single mobile device, cheapest tier available.',                                4, 2, 65.00,   'monthly',   'Bangladesh', 'active',  '2026-10-09', '2026-07-08 16:30:00'),
(27, 6, 6,  'Student Family',        'Verified student pricing on the family tier.',                                  6, 5, 90.00,   'monthly',   'Bangladesh', 'active',  '2026-11-28', '2026-07-10 12:45:00'),
(28, 6, 7,  'Canva Teams Quarterly', 'Team workspace billed every three months.',                                     5, 4, 580.00,  'quarterly', 'Global',     'active',  '2027-02-14', '2026-07-12 10:10:00'),
(29, 6, 10, 'Plus Shared',           'Subscription ended, listing kept for order history.',                           3, 2, 610.00,  'monthly',   'Global',     'expired', '2026-08-01', '2026-07-14 15:20:00'),
(30, 6, 12, 'Coursera Team',         'Team licence with progress reporting.',                                         5, 4, 400.00,  'monthly',   'Global',     'active',  '2027-01-31', '2026-07-16 11:55:00');

-- ---------------------------------------------------------------------
-- Coupons : one usable, one exhausted, one expired, one usable, one off
-- Each failure mode has a code so every validation branch is demonstrable
-- ---------------------------------------------------------------------
INSERT INTO Coupons (coupon_id, code, description, discount_percent, valid_from, valid_until, usage_limit, times_used, is_active) VALUES
(1, 'EIDSALE20',  'Eid campaign, 20 percent off any slot', 20, '2026-06-01', '2026-09-30', 100, 4, TRUE),
(2, 'NEW10',      'First-order discount, limited quantity', 10, '2026-01-01', '2026-12-31',   2, 2, TRUE),
(3, 'BOISHAKH15', 'Pohela Boishakh weekend offer',          15, '2026-04-01', '2026-04-14',  50, 1, TRUE),
(4, 'STUDENT25',  'Verified student discount',              25, '2026-08-01', '2026-12-31', 200, 3, TRUE),
(5, 'WELCOME5',   'Retired welcome offer',                   5, '2026-07-01', '2026-10-31', 500, 4, FALSE);

-- ---------------------------------------------------------------------
-- Orders : 50 purchases
-- total_amount = (unit_price * slots_ordered) - discount_amount
-- ---------------------------------------------------------------------
INSERT INTO Orders (order_id, buyer_id, listing_id, coupon_id, slots_ordered, unit_price, discount_amount, total_amount, order_status, payment_status, payment_method, payment_ref, placed_at) VALUES
(1,  7,  1,  1,    1, 320.00,   64.00,  256.00,  'Approved',  'paid',                 'bkash',  '8A7B2C91', '2026-07-02 14:20:00'),
(2,  7,  2,  NULL, 1, 145.00,    0.00,  145.00,  'Approved',  'paid',                 'bkash',  '2C9A0B77', '2026-07-05 09:10:00'),
(3,  7,  9,  5,    1, 260.00,   13.00,  247.00,  'Approved',  'paid',                 'nagad',  '5D1E9F04', '2026-07-11 17:35:00'),
(4,  7,  13, NULL, 1,  95.00,    0.00,   95.00,  'Approved',  'paid',                 'bkash',  '71B3C8A2', '2026-07-19 11:50:00'),
(5,  7,  21, 4,    1, 175.00,   43.75,  131.25, 'Approved',  'paid',                 'nagad',  '9E4F1A63', '2026-08-02 13:05:00'),
(6,  7,  3,  NULL, 2, 210.00,    0.00,  420.00,  'Pending',   'unpaid',               NULL,     NULL,       '2026-08-20 19:40:00'),
(7,  8,  3,  2,    2, 210.00,   42.00,  378.00,  'Approved',  'paid',                 'bkash',  '7F1D4E22', '2026-06-14 10:15:00'),
(8,  8,  5,  NULL, 1, 590.00,    0.00,  590.00,  'Approved',  'paid',                 'rocket', '3A8D2B51', '2026-06-28 15:25:00'),
(9,  8,  11, 5,    1, 130.00,    6.50,  123.50, 'Approved',  'paid',                 'bkash',  '6C2A7E90', '2026-07-08 08:45:00'),
(10, 8,  14, NULL, 1, 125.00,    0.00,  125.00,  'Approved',  'paid',                 'nagad',  '4B9F0D13', '2026-07-23 16:00:00'),
(11, 8,  26, NULL, 1,  65.00,    0.00,   65.00,  'Approved',  'paid',                 'bkash',  '8D3E5C77', '2026-08-06 12:30:00'),
(12, 8,  7,  NULL, 1, 240.00,    0.00,  240.00,  'Pending',   'pending_verification', 'bkash',  '1F6A9B04', '2026-08-21 18:10:00'),
(13, 9,  2,  NULL, 1, 145.00,    0.00,  145.00,  'Approved',  'paid',                 'bkash',  '2C9A0B78', '2026-06-19 14:55:00'),
(14, 9,  19, 1,    1, 150.00,   30.00,  120.00,  'Approved',  'paid',                 'nagad',  '5E7C3A11', '2026-07-01 10:05:00'),
(15, 9,  23, NULL, 1,  99.00,    0.00,   99.00,  'Approved',  'paid',                 'bkash',  '9A1B4D66', '2026-07-15 17:20:00'),
(16, 9,  6,  NULL, 1, 180.00,    0.00,  180.00,  'Approved',  'paid',                 'rocket', '3C8E2F40', '2026-07-29 09:35:00'),
(17, 9,  30, 4,    1, 400.00,  100.00,  300.00,  'Approved',  'paid',                 'bkash',  '7B5D1E28', '2026-08-11 15:45:00'),
(18, 9,  12, NULL, 1, 620.00,    0.00,  620.00,  'Rejected',  'refunded',             'nagad',  '4D2A8C95', '2026-08-04 11:25:00'),
(19, 10, 1,  NULL, 1, 320.00,    0.00,  320.00,  'Approved',  'paid',                 'bkash',  '6E9F3B72', '2026-06-22 13:40:00'),
(20, 10, 4,  3,    1, 480.00,   72.00,  408.00,  'Approved',  'paid',                 'nagad',  '1A4C7D30', '2026-04-10 16:15:00'),
(21, 10, 16, NULL, 2, 300.00,    0.00,  600.00,  'Approved',  'paid',                 'bkash',  '8F2B6A54', '2026-07-06 08:20:00'),
(22, 10, 27, NULL, 1,  90.00,    0.00,   90.00,  'Approved',  'paid',                 'bkash',  '5C1D9E83', '2026-08-09 14:00:00'),
(23, 10, 18, NULL, 1, 420.00,    0.00,  420.00,  'Pending',   'pending_verification', 'nagad',  '2B7E4F19', '2026-08-22 10:30:00'),
(24, 11, 4,  NULL, 1, 480.00,    0.00,  480.00,  'Rejected',  'refunded',             NULL,     NULL,       '2026-08-12 19:05:00'),
(25, 11, 8,  NULL, 1, 110.00,    0.00,  110.00,  'Approved',  'paid',                 'bkash',  '9D6A2C47', '2026-06-30 11:45:00'),
(26, 11, 20, 1,    1, 390.00,   78.00,  312.00,  'Approved',  'paid',                 'nagad',  '3E8B1F65', '2026-07-17 15:10:00'),
(27, 11, 28, NULL, 1, 580.00,    0.00,  580.00,  'Approved',  'paid',                 'rocket', '7A3C9D02', '2026-08-01 09:25:00'),
(28, 11, 22, NULL, 1, 310.00,    0.00,  310.00,  'Cancelled', 'unpaid',               NULL,     NULL,       '2026-08-15 17:50:00'),
(29, 12, 1,  2,    1, 320.00,   32.00,  288.00,  'Approved',  'paid',                 'bkash',  '4F1E8B36', '2026-05-28 12:35:00'),
(30, 12, 2,  NULL, 1, 145.00,    0.00,  145.00,  'Approved',  'paid',                 'bkash',  '6B9D3A81', '2026-06-11 16:20:00'),
(31, 12, 15, 4,    1, 1900.00, 475.00, 1425.00,  'Approved',  'paid',                 'nagad',  '2D7F5C14', '2026-07-04 10:55:00'),
(32, 12, 17, NULL, 1, 640.00,    0.00,  640.00,  'Approved',  'paid',                 'rocket', '8C4A1E79', '2026-07-26 14:30:00'),
(33, 12, 24, NULL, 1, 5800.00,   0.00, 5800.00,  'Pending',   'unpaid',               NULL,     NULL,       '2026-08-18 18:45:00'),
(34, 13, 6,  NULL, 1, 180.00,    0.00,  180.00,  'Approved',  'paid',                 'bkash',  '1E5B8D43', '2026-06-05 09:40:00'),
(35, 13, 11, NULL, 2, 130.00,    0.00,  260.00,  'Approved',  'paid',                 'nagad',  '9F2C6A50', '2026-06-27 13:15:00'),
(36, 13, 13, 5,    1,  95.00,    4.75,   90.25, 'Approved',  'paid',                 'bkash',  '3B8E1D97', '2026-07-13 17:00:00'),
(37, 13, 25, NULL, 1, 3400.00,   0.00, 3400.00,  'Approved',  'paid',                 'rocket', '5A7D4F22', '2026-07-31 11:20:00'),
(38, 13, 29, NULL, 1, 610.00,    0.00,  610.00,  'Approved',  'paid',                 'bkash',  '7C1A9B68', '2026-07-20 15:35:00'),
(39, 14, 3,  NULL, 1, 210.00,    0.00,  210.00,  'Approved',  'paid',                 'bkash',  '2F6D3C85', '2026-06-16 08:50:00'),
(40, 14, 10, 1,    1, 350.00,   70.00,  280.00,  'Approved',  'paid',                 'nagad',  '8B4E7A11', '2026-07-09 12:05:00'),
(41, 14, 14, NULL, 1, 125.00,    0.00,  125.00,  'Approved',  'paid',                 'bkash',  '4D9C2E56', '2026-07-27 16:40:00'),
(42, 14, 19, NULL, 1, 150.00,    0.00,  150.00,  'Approved',  'paid',                 'bkash',  '6A3F8D74', '2026-08-08 10:15:00'),
(43, 14, 21, NULL, 1, 175.00,    0.00,  175.00,  'Pending',   'unpaid',               NULL,     NULL,       '2026-08-21 20:00:00'),
(44, 15, 5,  NULL, 1, 590.00,    0.00,  590.00,  'Approved',  'paid',                 'rocket', '1C8B5A39', '2026-06-02 14:10:00'),
(45, 15, 9,  NULL, 1, 260.00,    0.00,  260.00,  'Approved',  'paid',                 'bkash',  '9E7D1F42', '2026-06-24 09:55:00'),
(46, 15, 23, 5,    1,  99.00,    4.95,   94.05, 'Approved',  'paid',                 'bkash',  '3A2C6E88', '2026-07-14 13:30:00'),
(47, 15, 26, NULL, 1,  65.00,    0.00,   65.00,  'Approved',  'paid',                 'nagad',  '7D5B9C03', '2026-08-05 17:45:00'),
(48, 16, 7,  NULL, 1, 240.00,    0.00,  240.00,  'Approved',  'paid',                 'bkash',  '5F1A4D67', '2026-07-03 11:00:00'),
(49, 16, 16, NULL, 1, 300.00,    0.00,  300.00,  'Approved',  'paid',                 'bkash',  '8E6C2B95', '2026-07-21 15:55:00'),
(50, 16, 30, NULL, 1, 400.00,    0.00,  400.00,  'Cancelled', 'unpaid',               NULL,     NULL,       '2026-08-19 12:25:00');

-- ---------------------------------------------------------------------
-- OrderStatusHistory
-- Row 1 for every order: the moment the buyer placed it.
-- Row 2 only where the order later moved away from Pending.
-- Generated with INSERT ... SELECT so the trail can never drift
-- out of sync with the Orders table.
-- ---------------------------------------------------------------------
INSERT INTO OrderStatusHistory (order_id, old_status, new_status, changed_by, reason, changed_at)
SELECT order_id, NULL, 'Pending', buyer_id, 'Order placed by buyer', placed_at
FROM Orders
ORDER BY order_id;

INSERT INTO OrderStatusHistory (order_id, old_status, new_status, changed_by, reason, changed_at)
SELECT
    order_id,
    'Pending',
    order_status,
    CASE WHEN order_status = 'Cancelled' THEN buyer_id ELSE 1 END,
    CASE order_status
        WHEN 'Approved'  THEN 'Payment reference verified, slot released to buyer'
        WHEN 'Rejected'  THEN 'Payment reference could not be verified with the seller'
        WHEN 'Cancelled' THEN 'Cancelled by the buyer before verification'
    END,
    placed_at + INTERVAL 1 DAY
FROM Orders
WHERE order_status <> 'Pending'
ORDER BY order_id;

-- ---------------------------------------------------------------------
-- Reviews : 25 ratings, only from buyers with an approved order
-- UNIQUE(reviewer_id, listing_id) means nobody can rate twice
-- ---------------------------------------------------------------------
INSERT INTO Reviews (reviewer_id, listing_id, rating, comment, created_at) VALUES
(7,  1,  5, 'Seller added me within an hour. No password changes so far.',              '2026-07-04 18:20:00'),
(7,  2,  4, 'Good value. Took two days to get the invite though.',                      '2026-07-08 12:15:00'),
(7,  9,  5, 'Shared libraries work exactly as described.',                              '2026-07-14 09:40:00'),
(7,  13, 3, 'Cheap, but the stream drops during live matches.',                         '2026-07-22 20:05:00'),
(8,  3,  5, 'Brand kit access was instant. Would buy again.',                           '2026-06-18 11:30:00'),
(8,  5,  4, 'Fast responses, though the seller paused the plan later.',                 '2026-07-02 15:50:00'),
(8,  11, 4, 'Delivery benefits were a nice bonus on top of video.',                     '2026-07-12 08:25:00'),
(8,  26, 5, 'Cheapest mobile tier I could find anywhere.',                              '2026-08-10 17:10:00'),
(9,  2,  5, 'Six separate accounts, no interference between profiles.',                 '2026-06-23 13:45:00'),
(9,  19, 4, 'Parental controls were already configured. Helpful.',                      '2026-07-05 10:20:00'),
(9,  23, 3, 'Works, but buffering in the evenings.',                                    '2026-07-19 19:35:00'),
(9,  30, 5, 'Progress reporting is genuinely useful for group study.',                  '2026-08-15 14:00:00'),
(10, 1,  4, 'Smooth handover. Renewal reminder arrived on time.',                       '2026-06-26 16:40:00'),
(10, 4,  5, 'Full suite for a fraction of the retail price.',                           '2026-04-15 09:15:00'),
(10, 16, 4, 'Invite came through in about forty minutes.',                              '2026-07-10 12:50:00'),
(10, 27, 5, 'Student pricing verified without any trouble.',                            '2026-08-13 18:30:00'),
(11, 8,  4, 'Simple two-person plan, no complications.',                                '2026-07-04 11:05:00'),
(11, 20, 5, 'Lightroom sync worked immediately across devices.',                        '2026-07-21 15:20:00'),
(11, 28, 4, 'Team workspace is well organised.',                                        '2026-08-05 10:45:00'),
(12, 1,  5, 'Third month on this plan, still no issues.',                               '2026-06-01 14:25:00'),
(12, 15, 5, 'Annual pricing works out far cheaper than monthly.',                       '2026-07-08 17:55:00'),
(13, 6,  4, 'Background play is the main reason I joined.',                             '2026-06-09 08:35:00'),
(13, 11, 5, 'Two slots, both activated same day.',                                      '2026-07-01 13:10:00'),
(14, 10, 4, 'Certificates unlocked as promised.',                                       '2026-07-13 16:05:00'),
(15, 9,  5, 'Dev mode access is exactly what I needed.',                                '2026-06-28 09:50:00');

-- ---------------------------------------------------------------------
-- SharedGroups : the people actually sharing each account
-- ---------------------------------------------------------------------
INSERT INTO SharedGroups (group_id, listing_id, owner_id, group_name, max_members, created_at) VALUES
(1, 1,  2, 'Netflix Dhaka Squad',     4, '2026-06-20 10:00:00'),
(2, 2,  2, 'Spotify Campus',          6, '2026-06-21 11:15:00'),
(3, 3,  2, 'Canva Design Club',       5, '2026-06-22 09:30:00'),
(4, 7,  3, 'Netflix Standard Circle', 4, '2026-07-01 14:20:00'),
(5, 11, 3, 'Prime Household BD',      6, '2026-07-03 16:45:00'),
(6, 14, 4, 'Apple Music Family',      6, '2026-07-05 08:50:00'),
(7, 19, 5, 'Spotify Bundle Crew',     6, '2026-07-07 13:05:00'),
(8, 26, 6, 'Hotstar Mobile Group',    4, '2026-07-09 17:25:00');

-- ---------------------------------------------------------------------
-- GroupMembers : composite primary key (group_id, user_id)
-- Group 1 is deliberately full so the "group is full" path is demonstrable
-- ---------------------------------------------------------------------
INSERT INTO GroupMembers (group_id, user_id, joined_at) VALUES
(1, 2,  '2026-06-20 10:00:00'),
(1, 7,  '2026-07-03 09:15:00'),
(1, 10, '2026-06-23 14:30:00'),
(1, 12, '2026-05-29 11:40:00'),
(2, 2,  '2026-06-21 11:15:00'),
(2, 7,  '2026-07-06 10:20:00'),
(2, 9,  '2026-06-20 15:05:00'),
(2, 12, '2026-06-12 17:35:00'),
(3, 2,  '2026-06-22 09:30:00'),
(3, 8,  '2026-06-15 12:45:00'),
(3, 14, '2026-06-17 08:10:00'),
(4, 3,  '2026-07-01 14:20:00'),
(4, 16, '2026-07-04 13:55:00'),
(5, 3,  '2026-07-03 16:45:00'),
(5, 8,  '2026-07-09 09:25:00'),
(5, 13, '2026-06-28 16:00:00'),
(6, 4,  '2026-07-05 08:50:00'),
(6, 8,  '2026-07-24 11:30:00'),
(6, 14, '2026-07-28 15:15:00'),
(7, 5,  '2026-07-07 13:05:00'),
(7, 9,  '2026-07-02 10:40:00'),
(7, 14, '2026-08-09 12:20:00'),
(8, 6,  '2026-07-09 17:25:00'),
(8, 8,  '2026-08-07 14:05:00'),
(8, 15, '2026-08-06 18:50:00');

-- ---------------------------------------------------------------------
-- Wishlist : saved listings, composite primary key (user_id, listing_id)
-- ---------------------------------------------------------------------
INSERT INTO Wishlist (user_id, listing_id, added_at) VALUES
(7,  5,  '2026-08-18 10:30:00'),
(7,  17, '2026-08-12 15:45:00'),
(7,  24, '2026-08-19 09:20:00'),
(8,  1,  '2026-08-15 13:10:00'),
(8,  20, '2026-08-03 17:25:00'),
(8,  25, '2026-08-16 11:50:00'),
(9,  4,  '2026-08-07 08:40:00'),
(9,  12, '2026-08-14 19:15:00'),
(10, 5,  '2026-08-11 12:00:00'),
(10, 28, '2026-08-17 16:35:00'),
(11, 1,  '2026-08-09 10:05:00'),
(11, 15, '2026-08-20 14:50:00'),
(12, 13, '2026-08-06 18:20:00'),
(12, 30, '2026-08-13 09:45:00'),
(13, 3,  '2026-08-21 15:30:00');

-- ---------------------------------------------------------------------
-- Notifications : written by other features, never by a direct user action
-- ---------------------------------------------------------------------
INSERT INTO Notifications (user_id, title, message, type, is_read, created_at) VALUES
(7,  'Order #1 approved',            'Your Netflix Premium 4K UHD slot is confirmed. The seller will send the invite shortly.', 'order',    TRUE,  '2026-07-03 09:00:00'),
(7,  'A slot opened on Plus Team',   'A listing on your saved list now has availability.',                                     'wishlist', FALSE, '2026-08-19 08:15:00'),
(7,  'Order #6 received',            'We have your order. It stays pending until your payment reference is verified.',         'order',    FALSE, '2026-08-20 19:40:00'),
(8,  'Order #7 approved',            'Your Canva Pro Teams slots are confirmed.',                                              'order',    TRUE,  '2026-06-15 10:15:00'),
(8,  'You joined Hotstar Mobile Group', 'You are now a member. The group has 3 of 4 members.',                                 'group',    TRUE,  '2026-08-07 14:05:00'),
(8,  'Order #12 awaiting review',    'Your payment reference has been submitted and is waiting for verification.',             'order',    FALSE, '2026-08-21 18:10:00'),
(9,  'Order #18 rejected',           'The payment reference could not be verified with the seller. A refund was processed.',   'order',    TRUE,  '2026-08-05 11:25:00'),
(9,  'Order #17 approved',           'Your Coursera Team slot is confirmed.',                                                  'order',    FALSE, '2026-08-12 15:45:00'),
(10, 'Order #23 awaiting review',    'Your payment reference has been submitted and is waiting for verification.',             'order',    FALSE, '2026-08-22 10:30:00'),
(10, 'Farhana joined Spotify Bundle Crew', 'A group you are watching now has 3 of 6 members.',                                 'group',    TRUE,  '2026-08-09 12:20:00'),
(11, 'Order #24 rejected',           'The payment reference could not be verified with the seller. A refund was processed.',   'order',    TRUE,  '2026-08-13 19:05:00'),
(11, 'Order #28 cancelled',          'You cancelled this order before verification.',                                          'order',    TRUE,  '2026-08-15 17:50:00'),
(12, 'Order #33 received',           'We have your order. It stays pending until your payment reference is verified.',         'order',    FALSE, '2026-08-18 18:45:00'),
(12, 'Price drop on Super Plan',     'A listing on your saved list is now cheaper than when you saved it.',                    'wishlist', FALSE, '2026-08-14 10:10:00'),
(13, 'Order #38 approved',           'Your Plus Shared slot is confirmed.',                                                    'order',    TRUE,  '2026-07-21 15:35:00'),
(13, 'A slot opened on Pro Teams',   'A listing on your saved list now has availability.',                                     'wishlist', FALSE, '2026-08-21 15:30:00'),
(14, 'Order #43 received',           'We have your order. It stays pending until your payment reference is verified.',         'order',    FALSE, '2026-08-21 20:00:00'),
(15, 'You joined Hotstar Mobile Group', 'You are now a member. The group has 3 of 4 members.',                                 'group',    TRUE,  '2026-08-06 18:50:00'),
(16, 'Order #50 cancelled',          'You cancelled this order before verification.',                                          'order',    FALSE, '2026-08-19 12:25:00'),
(2,  'New order on Premium 4K UHD',  'A buyer has placed an order on one of your listings.',                                   'order',    FALSE, '2026-08-20 19:40:00');
