-- =====================================================================
-- Sub-Share : data integrity check
-- Run after schema.sql + seed.sql, or any time the data has been edited.
--
-- Section 1 prints the row count of every table.
-- Sections 2 to 5 must all return ZERO rows. Any row returned is a bug.
-- =====================================================================

USE split_share;

-- 1. Row counts -------------------------------------------------------
SELECT 'Users'              AS table_name, COUNT(*) AS rows_found FROM Users
UNION ALL SELECT 'Categories',         COUNT(*) FROM Categories
UNION ALL SELECT 'Platforms',          COUNT(*) FROM Platforms
UNION ALL SELECT 'Listings',           COUNT(*) FROM Listings
UNION ALL SELECT 'Coupons',            COUNT(*) FROM Coupons
UNION ALL SELECT 'Orders',             COUNT(*) FROM Orders
UNION ALL SELECT 'OrderStatusHistory', COUNT(*) FROM OrderStatusHistory
UNION ALL SELECT 'Reviews',            COUNT(*) FROM Reviews
UNION ALL SELECT 'SharedGroups',       COUNT(*) FROM SharedGroups
UNION ALL SELECT 'GroupMembers',       COUNT(*) FROM GroupMembers
UNION ALL SELECT 'Wishlist',           COUNT(*) FROM Wishlist
UNION ALL SELECT 'Notifications',      COUNT(*) FROM Notifications;

-- 2. available_slots must equal total_slots minus approved slots ------
SELECT 'BAD SLOT COUNT' AS problem, l.listing_id, l.total_slots,
       l.available_slots, COALESCE(SUM(o.slots_ordered), 0) AS approved_slots
FROM Listings l
LEFT JOIN Orders o
       ON o.listing_id = l.listing_id
      AND o.order_status = 'Approved'
GROUP BY l.listing_id, l.total_slots, l.available_slots
HAVING l.available_slots != l.total_slots - COALESCE(SUM(o.slots_ordered), 0);

-- 3. times_used must equal the number of orders using that coupon -----
SELECT 'BAD COUPON COUNTER' AS problem, c.coupon_id, c.code,
       c.times_used, COUNT(o.order_id) AS actual_uses
FROM Coupons c
LEFT JOIN Orders o ON o.coupon_id = c.coupon_id
GROUP BY c.coupon_id, c.code, c.times_used
HAVING c.times_used != COUNT(o.order_id);

-- 4. A review must be backed by an approved order ---------------------
SELECT 'REVIEW WITHOUT PURCHASE' AS problem, r.review_id,
       r.reviewer_id, r.listing_id
FROM Reviews r
WHERE NOT EXISTS (
    SELECT 1 FROM Orders o
    WHERE o.buyer_id   = r.reviewer_id
      AND o.listing_id = r.listing_id
      AND o.order_status = 'Approved'
);

-- 5. A group must never hold more members than max_members ------------
SELECT 'GROUP OVER CAPACITY' AS problem, g.group_id, g.group_name,
       g.max_members, COUNT(m.user_id) AS current_members
FROM SharedGroups g
LEFT JOIN GroupMembers m ON m.group_id = g.group_id
GROUP BY g.group_id, g.group_name, g.max_members
HAVING COUNT(m.user_id) > g.max_members;

-- 6. Every order must have at least one history row -------------------
SELECT 'ORDER WITHOUT HISTORY' AS problem, o.order_id
FROM Orders o
WHERE NOT EXISTS (
    SELECT 1 FROM OrderStatusHistory h WHERE h.order_id = o.order_id
);
