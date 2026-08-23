-- =====================================================================
-- Sub-Share : database schema
-- Engine  : MariaDB 10.4+ / MySQL 8.0+ (InnoDB, utf8mb4)
-- Tables  : 12
-- Notes   : This file is the single source of truth for the database.
--           Re-running it drops and rebuilds everything from scratch.
--           Constraints used: PRIMARY KEY, FOREIGN KEY, NOT NULL, UNIQUE,
--           DEFAULT and AUTO_INCREMENT. Value ranges are validated in the
--           application layer and audited by db/verify.sql.
-- =====================================================================

DROP DATABASE IF EXISTS split_share;
CREATE DATABASE split_share
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;
USE split_share;

SET FOREIGN_KEY_CHECKS = 0;

-- ---------------------------------------------------------------------
-- 1. Users
--    Everyone who can log in: buyers, sellers and administrators.
-- ---------------------------------------------------------------------
CREATE TABLE Users (
    user_id       INT AUTO_INCREMENT PRIMARY KEY,
    first_name    VARCHAR(50)  NOT NULL,
    last_name     VARCHAR(50)  NOT NULL,
    email         VARCHAR(120) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    phone         VARCHAR(20)      NULL,
    role          ENUM('buyer','seller','admin') NOT NULL DEFAULT 'buyer',
    is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_users_email UNIQUE (email)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 2. Categories
--    Broad groupings shown as filter pills on the browse page.
-- ---------------------------------------------------------------------
CREATE TABLE Categories (
    category_id INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(60)  NOT NULL,
    description VARCHAR(255)     NULL,

    CONSTRAINT uq_categories_name UNIQUE (name)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 3. Platforms
--    The actual services being shared. Each platform sits in one category.
-- ---------------------------------------------------------------------
CREATE TABLE Platforms (
    platform_id INT AUTO_INCREMENT PRIMARY KEY,
    category_id INT          NOT NULL,
    name        VARCHAR(80)  NOT NULL,
    brand_color VARCHAR(7)       NULL,
    website     VARCHAR(150)     NULL,

    CONSTRAINT uq_platforms_name UNIQUE (name),
    CONSTRAINT fk_platforms_category
        FOREIGN KEY (category_id) REFERENCES Categories(category_id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 4. Listings
--    One seller offering slots on one plan.
--    available_slots is stored, not calculated, so browse stays fast.
-- ---------------------------------------------------------------------
CREATE TABLE Listings (
    listing_id      INT AUTO_INCREMENT PRIMARY KEY,
    seller_id       INT            NOT NULL,
    platform_id     INT            NOT NULL,
    plan_name       VARCHAR(100)   NOT NULL,
    description     TEXT               NULL,
    total_slots     TINYINT UNSIGNED NOT NULL,
    available_slots TINYINT UNSIGNED NOT NULL,
    price_per_slot  DECIMAL(10,2)  NOT NULL,
    billing_cycle   ENUM('monthly','quarterly','yearly') NOT NULL DEFAULT 'monthly',
    region          VARCHAR(60)    NOT NULL DEFAULT 'Bangladesh',
    status          ENUM('active','paused','expired') NOT NULL DEFAULT 'active',
    expires_on      DATE               NULL,
    created_at      DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_listings_seller
        FOREIGN KEY (seller_id) REFERENCES Users(user_id),
    CONSTRAINT fk_listings_platform
        FOREIGN KEY (platform_id) REFERENCES Platforms(platform_id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 5. Coupons
--    Discount codes applied at checkout.
--    times_used is a counter the checkout transaction increments.
-- ---------------------------------------------------------------------
CREATE TABLE Coupons (
    coupon_id        INT AUTO_INCREMENT PRIMARY KEY,
    code             VARCHAR(30)   NOT NULL,
    description      VARCHAR(150)      NULL,
    discount_percent TINYINT UNSIGNED NOT NULL,
    valid_from       DATE          NOT NULL,
    valid_until      DATE          NOT NULL,
    usage_limit      INT UNSIGNED  NOT NULL DEFAULT 100,
    times_used       INT UNSIGNED  NOT NULL DEFAULT 0,
    is_active        BOOLEAN       NOT NULL DEFAULT TRUE,

    CONSTRAINT uq_coupons_code UNIQUE (code)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 6. Orders
--    One purchase of one or more slots on one listing.
--    Payment is collected off-platform; only the reference is stored here.
-- ---------------------------------------------------------------------
CREATE TABLE Orders (
    order_id        INT AUTO_INCREMENT PRIMARY KEY,
    buyer_id        INT           NOT NULL,
    listing_id      INT           NOT NULL,
    coupon_id       INT               NULL,
    slots_ordered   TINYINT UNSIGNED NOT NULL DEFAULT 1,
    unit_price      DECIMAL(10,2) NOT NULL,
    discount_amount DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    total_amount    DECIMAL(10,2) NOT NULL,
    order_status    ENUM('Pending','Approved','Rejected','Cancelled')
                    NOT NULL DEFAULT 'Pending',
    payment_status  ENUM('unpaid','pending_verification','paid','refunded')
                    NOT NULL DEFAULT 'unpaid',
    payment_method  ENUM('bkash','nagad','rocket') NULL,
    payment_ref     VARCHAR(60)       NULL,
    placed_at       DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_orders_buyer
        FOREIGN KEY (buyer_id) REFERENCES Users(user_id),
    CONSTRAINT fk_orders_listing
        FOREIGN KEY (listing_id) REFERENCES Listings(listing_id),
    CONSTRAINT fk_orders_coupon
        FOREIGN KEY (coupon_id) REFERENCES Coupons(coupon_id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 7. OrderStatusHistory
--    Append-only audit trail. Order status is never silently overwritten.
-- ---------------------------------------------------------------------
CREATE TABLE OrderStatusHistory (
    history_id  INT AUTO_INCREMENT PRIMARY KEY,
    order_id    INT      NOT NULL,
    old_status  ENUM('Pending','Approved','Rejected','Cancelled') NULL,
    new_status  ENUM('Pending','Approved','Rejected','Cancelled') NOT NULL,
    changed_by  INT          NULL,
    reason      VARCHAR(255) NULL,
    changed_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_history_order
        FOREIGN KEY (order_id) REFERENCES Orders(order_id),
    CONSTRAINT fk_history_user
        FOREIGN KEY (changed_by) REFERENCES Users(user_id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 8. Reviews
--    One rating per buyer per listing, enforced by a unique pair.
-- ---------------------------------------------------------------------
CREATE TABLE Reviews (
    review_id   INT AUTO_INCREMENT PRIMARY KEY,
    reviewer_id INT             NOT NULL,
    listing_id  INT             NOT NULL,
    rating      TINYINT UNSIGNED NOT NULL,
    comment     VARCHAR(500)        NULL,
    created_at  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_review_once UNIQUE (reviewer_id, listing_id),
    CONSTRAINT fk_reviews_user
        FOREIGN KEY (reviewer_id) REFERENCES Users(user_id),
    CONSTRAINT fk_reviews_listing
        FOREIGN KEY (listing_id) REFERENCES Listings(listing_id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 9. SharedGroups
--    The people-side of a listing: who is actually sharing the account.
-- ---------------------------------------------------------------------
CREATE TABLE SharedGroups (
    group_id    INT AUTO_INCREMENT PRIMARY KEY,
    listing_id  INT             NOT NULL,
    owner_id    INT             NOT NULL,
    group_name  VARCHAR(100)    NOT NULL,
    max_members TINYINT UNSIGNED NOT NULL,
    created_at  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_groups_listing
        FOREIGN KEY (listing_id) REFERENCES Listings(listing_id),
    CONSTRAINT fk_groups_owner
        FOREIGN KEY (owner_id) REFERENCES Users(user_id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 10. GroupMembers
--     Junction table. The pair (group_id, user_id) is the primary key,
--     so the same person cannot join the same group twice.
-- ---------------------------------------------------------------------
CREATE TABLE GroupMembers (
    group_id  INT      NOT NULL,
    user_id   INT      NOT NULL,
    joined_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (group_id, user_id),
    CONSTRAINT fk_members_group
        FOREIGN KEY (group_id) REFERENCES SharedGroups(group_id),
    CONSTRAINT fk_members_user
        FOREIGN KEY (user_id) REFERENCES Users(user_id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 11. Wishlist
--     Junction table with the same composite-key trick as GroupMembers.
-- ---------------------------------------------------------------------
CREATE TABLE Wishlist (
    user_id    INT      NOT NULL,
    listing_id INT      NOT NULL,
    added_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (user_id, listing_id),
    CONSTRAINT fk_wishlist_user
        FOREIGN KEY (user_id) REFERENCES Users(user_id),
    CONSTRAINT fk_wishlist_listing
        FOREIGN KEY (listing_id) REFERENCES Listings(listing_id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 12. Notifications
--     Written by other features, never directly by a user action.
-- ---------------------------------------------------------------------
CREATE TABLE Notifications (
    notification_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id         INT          NOT NULL,
    title           VARCHAR(120) NOT NULL,
    message         VARCHAR(400) NOT NULL,
    type            ENUM('order','group','wishlist','system') NOT NULL DEFAULT 'system',
    is_read         BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_notifications_user
        FOREIGN KEY (user_id) REFERENCES Users(user_id)
) ENGINE=InnoDB;

SET FOREIGN_KEY_CHECKS = 1;
