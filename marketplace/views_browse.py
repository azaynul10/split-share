"""
The catalogue: browse with search, filters and sorting, plus listing detail.

Two things to note about the SQL here.

1. The WHERE clause is assembled from whichever filters the user actually
   submitted, but every user value is still passed as a %s parameter. The SQL
   text itself never contains user input.

2. Sorting cannot be parameterised, because ORDER BY takes an identifier and
   not a value. So sort keys are looked up in SORT_OPTIONS and anything not on
   that list falls back to the default. The user's string is never interpolated
   into the query.
"""

from django.contrib import messages
from django.shortcuts import redirect, render

from .db_utils import QueryError, fetch_all, fetch_one

PAGE_SIZE = 9

# ---------------------------------------------------------------------------
# Shared query fragments
# ---------------------------------------------------------------------------
LISTING_JOINS = """
    FROM Listings l
    INNER JOIN Platforms  p ON p.platform_id = l.platform_id
    INNER JOIN Categories c ON c.category_id = p.category_id
    INNER JOIN Users      u ON u.user_id     = l.seller_id
    LEFT  JOIN Reviews    r ON r.listing_id  = l.listing_id
"""

LISTING_COLUMNS = """
    SELECT
        l.listing_id,
        l.plan_name,
        l.total_slots,
        l.available_slots,
        l.price_per_slot,
        l.billing_cycle,
        l.region,
        l.expires_on,
        l.created_at,
        p.platform_id,
        p.name        AS platform_name,
        p.brand_color AS brand_color,
        c.category_id,
        c.name        AS category_name,
        u.user_id     AS seller_id,
        CONCAT(u.first_name, ' ', u.last_name) AS seller_name,
        ROUND(AVG(r.rating), 1) AS avg_rating,
        COUNT(r.review_id)      AS review_count
"""

LISTING_GROUP_BY = """
    GROUP BY
        l.listing_id, l.plan_name, l.total_slots, l.available_slots,
        l.price_per_slot, l.billing_cycle, l.region, l.expires_on,
        l.created_at, p.platform_id, p.name, p.brand_color,
        c.category_id, c.name, u.user_id, u.first_name, u.last_name
"""

# Sorting is whitelisted: key -> (label shown in the dropdown, ORDER BY clause)
SORT_OPTIONS = {
    "newest": ("Newest first", "l.created_at DESC, l.listing_id DESC"),
    "price_low": ("Price: low to high", "l.price_per_slot ASC, l.listing_id ASC"),
    "price_high": ("Price: high to low", "l.price_per_slot DESC, l.listing_id ASC"),
    "rating": (
        "Highest rated",
        "avg_rating DESC, review_count DESC, l.listing_id ASC",
    ),
}
DEFAULT_SORT = "newest"

BILLING_CYCLES = ("monthly", "quarterly", "yearly")

SELECT_CATEGORIES = """
    SELECT
        c.category_id,
        c.name,
        COUNT(l.listing_id) AS listing_count
    FROM Categories c
    LEFT JOIN Platforms p ON p.category_id = c.category_id
    LEFT JOIN Listings  l ON l.platform_id = p.platform_id
                         AND l.status = 'active'
    GROUP BY c.category_id, c.name
    ORDER BY c.name
"""

SELECT_PRICE_BOUNDS = """
    SELECT
        MIN(price_per_slot) AS min_price,
        MAX(price_per_slot) AS max_price
    FROM Listings
    WHERE status = 'active'
"""

SELECT_WISHLIST_IDS = """
    SELECT listing_id
    FROM Wishlist
    WHERE user_id = %s
"""


def _parse_decimal(raw):
    if raw in (None, ""):
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None


def _parse_int(raw):
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _build_filters(request):
    """Read the query string into a filters dict, a WHERE clause and params."""
    search = request.GET.get("q", "").strip()
    category_id = _parse_int(request.GET.get("category"))
    min_price = _parse_decimal(request.GET.get("min_price"))
    max_price = _parse_decimal(request.GET.get("max_price"))
    billing_cycle = request.GET.get("cycle", "")
    available_only = request.GET.get("available") == "1"
    min_rating = _parse_int(request.GET.get("min_rating"))
    sort = request.GET.get("sort", DEFAULT_SORT)

    if sort not in SORT_OPTIONS:
        sort = DEFAULT_SORT
    if billing_cycle not in BILLING_CYCLES:
        billing_cycle = ""
    if min_rating not in (1, 2, 3, 4, 5):
        min_rating = None
    if min_price is not None and max_price is not None and min_price > max_price:
        min_price, max_price = max_price, min_price

    where = ["l.status = 'active'"]
    params = []

    if search:
        where.append("(l.plan_name LIKE %s OR p.name LIKE %s OR c.name LIKE %s)")
        pattern = f"%{search}%"
        params.extend([pattern, pattern, pattern])

    if category_id:
        where.append("c.category_id = %s")
        params.append(category_id)

    if min_price is not None and max_price is not None:
        where.append("l.price_per_slot BETWEEN %s AND %s")
        params.extend([min_price, max_price])
    elif min_price is not None:
        where.append("l.price_per_slot >= %s")
        params.append(min_price)
    elif max_price is not None:
        where.append("l.price_per_slot <= %s")
        params.append(max_price)

    if billing_cycle:
        where.append("l.billing_cycle = %s")
        params.append(billing_cycle)

    if available_only:
        where.append("l.available_slots > 0")

    having = ""
    if min_rating:
        having = " HAVING AVG(r.rating) >= %s "

    filters = {
        "q": search,
        "category": category_id,
        "min_price": request.GET.get("min_price", ""),
        "max_price": request.GET.get("max_price", ""),
        "cycle": billing_cycle,
        "available": available_only,
        "min_rating": min_rating,
        "sort": sort,
    }

    return filters, "WHERE " + " AND ".join(where), params, having, min_rating


def _querystring_without_page(request):
    params = request.GET.copy()
    params.pop("page", None)
    encoded = params.urlencode()
    return f"&{encoded}" if encoded else ""


def _querystring_for_category(request):
    """Current filters as a query string, minus category and page.

    Each category pill appends its own `category=` value to this, so switching
    category keeps the price, rating and cycle filters the shopper already
    chose and sends them back to page one.
    """
    params = request.GET.copy()
    params.pop("page", None)
    params.pop("category", None)
    encoded = params.urlencode()
    return f"&{encoded}" if encoded else ""


def home(request):
    return redirect("browse")


def browse(request):
    filters, where_sql, where_params, having_sql, min_rating = _build_filters(request)
    page = max(1, _parse_int(request.GET.get("page")) or 1)

    having_params = [min_rating] if min_rating else []

    # Total matching rows. Because the rating filter lives in HAVING, the
    # grouped result is wrapped in a derived table and the rows counted.
    count_sql = f"""
        SELECT COUNT(*) AS total FROM (
            SELECT l.listing_id
            {LISTING_JOINS}
            {where_sql}
            GROUP BY l.listing_id
            {having_sql}
        ) AS filtered
    """

    listings_sql = f"""
        {LISTING_COLUMNS}
        {LISTING_JOINS}
        {where_sql}
        {LISTING_GROUP_BY}
        {having_sql}
        ORDER BY {SORT_OPTIONS[filters['sort']][1]}
        LIMIT %s OFFSET %s
    """

    listings = []
    total = 0
    categories = []
    price_bounds = {"min_price": None, "max_price": None}
    wishlist_ids = set()

    try:
        total_row = fetch_one(count_sql, where_params + having_params)
        total = int(total_row["total"]) if total_row else 0

        total_pages = max(1, -(-total // PAGE_SIZE))
        page = min(page, total_pages)
        offset = (page - 1) * PAGE_SIZE

        listings = fetch_all(
            listings_sql,
            where_params + having_params + [PAGE_SIZE, offset],
        )

        categories = fetch_all(SELECT_CATEGORIES)
        price_bounds = fetch_one(SELECT_PRICE_BOUNDS) or price_bounds

        if request.session.get("user_id"):
            rows = fetch_all(SELECT_WISHLIST_IDS, [request.session["user_id"]])
            wishlist_ids = {row["listing_id"] for row in rows}
    except QueryError:
        messages.error(
            request, "We could not load the catalogue. Please try again in a moment."
        )
        total_pages = 1
        page = 1

    for listing in listings:
        listing["in_wishlist"] = listing["listing_id"] in wishlist_ids

    selected_category = next(
        (row for row in categories if row["category_id"] == filters["category"]),
        None,
    )

    context = {
        "selected_category": selected_category,
        "listings": listings,
        "filters": filters,
        "categories": categories,
        "price_bounds": price_bounds,
        "sort_options": [(key, label) for key, (label, _) in SORT_OPTIONS.items()],
        "billing_cycles": BILLING_CYCLES,
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "page_range": range(1, total_pages + 1),
        "has_previous": page > 1,
        "has_next": page < total_pages,
        "querystring": _querystring_without_page(request),
        "category_querystring": _querystring_for_category(request),
        "catalogue_total": sum(row["listing_count"] for row in categories),
        "has_active_filters": any(
            [
                filters["q"],
                filters["category"],
                filters["min_price"],
                filters["max_price"],
                filters["cycle"],
                filters["available"],
                filters["min_rating"],
            ]
        ),
    }
    return render(request, "marketplace/browse.html", context)


# ---------------------------------------------------------------------------
# Listing detail
# ---------------------------------------------------------------------------
SELECT_LISTING_DETAIL = """
    SELECT
        l.listing_id,
        l.plan_name,
        l.description,
        l.total_slots,
        l.available_slots,
        l.price_per_slot,
        l.billing_cycle,
        l.region,
        l.status,
        l.expires_on,
        l.created_at,
        p.platform_id,
        p.name        AS platform_name,
        p.brand_color AS brand_color,
        p.website     AS platform_website,
        c.category_id,
        c.name        AS category_name,
        u.user_id     AS seller_id,
        CONCAT(u.first_name, ' ', u.last_name) AS seller_name,
        u.created_at  AS seller_joined,
        ROUND(AVG(r.rating), 1) AS avg_rating,
        COUNT(r.review_id)      AS review_count,
        (SELECT COUNT(*)
           FROM Wishlist w
          WHERE w.user_id = %s
            AND w.listing_id = l.listing_id) AS in_wishlist
    FROM Listings l
    INNER JOIN Platforms  p ON p.platform_id = l.platform_id
    INNER JOIN Categories c ON c.category_id = p.category_id
    INNER JOIN Users      u ON u.user_id     = l.seller_id
    LEFT  JOIN Reviews    r ON r.listing_id  = l.listing_id
    WHERE l.listing_id = %s
    GROUP BY
        l.listing_id, l.plan_name, l.description, l.total_slots,
        l.available_slots, l.price_per_slot, l.billing_cycle, l.region,
        l.status, l.expires_on, l.created_at,
        p.platform_id, p.name, p.brand_color, p.website,
        c.category_id, c.name,
        u.user_id, u.first_name, u.last_name, u.created_at
"""

SELECT_LISTING_REVIEWS = """
    SELECT
        r.review_id,
        r.rating,
        r.comment,
        r.created_at,
        CONCAT(u.first_name, ' ', u.last_name) AS reviewer_name
    FROM Reviews r
    INNER JOIN Users u ON u.user_id = r.reviewer_id
    WHERE r.listing_id = %s
    ORDER BY r.created_at DESC
"""

SELECT_RATING_BREAKDOWN = """
    SELECT rating, COUNT(*) AS votes
    FROM Reviews
    WHERE listing_id = %s
    GROUP BY rating
    ORDER BY rating DESC
"""

SELECT_SELLER_SUMMARY = """
    SELECT
        COUNT(DISTINCT l.listing_id) AS listing_count,
        ROUND(AVG(r.rating), 1)      AS seller_rating
    FROM Listings l
    LEFT JOIN Reviews r ON r.listing_id = l.listing_id
    WHERE l.seller_id = %s
"""

SELECT_RELATED_LISTINGS = """
    SELECT
        l.listing_id,
        l.plan_name,
        l.price_per_slot,
        l.available_slots,
        p.name        AS platform_name,
        p.brand_color AS brand_color,
        ROUND(AVG(r.rating), 1) AS avg_rating
    FROM Listings l
    INNER JOIN Platforms  p ON p.platform_id = l.platform_id
    LEFT  JOIN Reviews    r ON r.listing_id  = l.listing_id
    WHERE p.category_id = %s
      AND l.listing_id <> %s
      AND l.status = 'active'
    GROUP BY l.listing_id, l.plan_name, l.price_per_slot,
             l.available_slots, p.name, p.brand_color
    ORDER BY l.available_slots DESC, l.created_at DESC
    LIMIT 3
"""


def listing_detail(request, listing_id):
    viewer_id = request.session.get("user_id") or 0

    try:
        listing = fetch_one(SELECT_LISTING_DETAIL, [viewer_id, listing_id])
    except QueryError:
        messages.error(request, "We could not load that listing.")
        return redirect("browse")

    if listing is None or listing["listing_id"] is None:
        messages.error(request, "That listing does not exist.")
        return redirect("browse")

    reviews = []
    breakdown_map = {}
    seller = {"listing_count": 0, "seller_rating": None}
    related = []

    try:
        reviews = fetch_all(SELECT_LISTING_REVIEWS, [listing_id])
        breakdown_map = {
            int(row["rating"]): int(row["votes"])
            for row in fetch_all(SELECT_RATING_BREAKDOWN, [listing_id])
        }
        seller = fetch_one(SELECT_SELLER_SUMMARY, [listing["seller_id"]]) or seller
        related = fetch_all(
            SELECT_RELATED_LISTINGS, [listing["category_id"], listing_id]
        )
    except QueryError:
        messages.warning(request, "Some details on this page could not be loaded.")

    total_votes = sum(breakdown_map.values())
    breakdown = []
    for stars in (5, 4, 3, 2, 1):
        votes = breakdown_map.get(stars, 0)
        breakdown.append(
            {
                "stars": stars,
                "votes": votes,
                "percent": round(votes * 100 / total_votes) if total_votes else 0,
            }
        )

    context = {
        "listing": listing,
        "reviews": reviews,
        "breakdown": breakdown,
        "seller": seller,
        "related": related,
        "in_wishlist": bool(listing["in_wishlist"]),
        "sold_out": listing["available_slots"] == 0,
        "star_range": range(1, 6),
        "slot_choices": range(1, listing["available_slots"] + 1),
    }
    return render(request, "marketplace/listing_detail.html", context)
