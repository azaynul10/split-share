"""Shared Groups for buyers sharing the same subscription."""

from django.contrib import messages
from django.db import IntegrityError, connection, transaction
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .decorators import role_required_raw
from .db_utils import fetch_all, fetch_one

# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

SELECT_ALL_GROUPS = """
    SELECT 
        g.group_id, 
        g.group_name, 
        g.max_members,
        l.listing_id,
        l.plan_name,
        p.name AS platform_name,
        p.brand_color,
        u.first_name AS owner_name,
        COUNT(m.user_id) AS current_members
    FROM SharedGroups g
    INNER JOIN Listings l ON l.listing_id = g.listing_id
    INNER JOIN Platforms p ON p.platform_id = l.platform_id
    INNER JOIN Users u ON u.user_id = g.owner_id
    LEFT JOIN GroupMembers m ON m.group_id = g.group_id
    GROUP BY 
        g.group_id, g.group_name, g.max_members, 
        l.listing_id, l.plan_name, p.name, p.brand_color, u.first_name
    ORDER BY g.created_at DESC
"""

SELECT_USER_MEMBERSHIPS = """
    SELECT group_id FROM GroupMembers WHERE user_id = %s
"""

# Buyers are eligible if they have an approved order for the listing
SELECT_BUYER_ELIGIBLE_LISTINGS = """
    SELECT DISTINCT listing_id 
    FROM Orders 
    WHERE buyer_id = %s AND order_status = 'Approved'
"""

SELECT_SELLER_LISTINGS = """
    SELECT l.listing_id, l.plan_name, p.name AS platform_name
    FROM Listings l
    INNER JOIN Platforms p ON p.platform_id = l.platform_id
    WHERE l.seller_id = %s AND l.status = 'active'
    ORDER BY p.name, l.plan_name
"""


def groups_list(request):
    """Display all shared groups with their current capacity and user status."""
    user_id = request.session.get("user_id")
    role = request.session.get("role")
    
    groups = fetch_all(SELECT_ALL_GROUPS)
    
    user_memberships = set()
    eligible_listings = set()
    
    if user_id:
        # Which groups is the user already in?
        memberships = fetch_all(SELECT_USER_MEMBERSHIPS, [user_id])
        user_memberships = {row["group_id"] for row in memberships}
        
        # Which listings has the buyer paid for?
        if role == "buyer":
            eligible = fetch_all(SELECT_BUYER_ELIGIBLE_LISTINGS, [user_id])
            eligible_listings = {row["listing_id"] for row in eligible}

    for group in groups:
        group["is_member"] = group["group_id"] in user_memberships
        group["is_full"] = group["current_members"] >= group["max_members"]
        # Only buyers who bought this listing can join
        group["can_join"] = role == "buyer" and group["listing_id"] in eligible_listings and not group["is_member"] and not group["is_full"]

    context = {
        "groups": groups,
    }
    return render(request, "marketplace/groups.html", context)


@role_required_raw("seller")
def create_group(request):
    """Form to create a new shared group."""
    seller_id = request.session["user_id"]
    
    if request.method == "POST":
        group_name = request.POST.get("group_name", "").strip()
        listing_id = request.POST.get("listing_id")
        max_members = request.POST.get("max_members")
        
        if not group_name or not listing_id or not max_members:
            messages.error(request, "Please fill in all fields.")
            return redirect("create_group")
            
        try:
            max_members = int(max_members)
            if max_members < 2 or max_members > 100:
                raise ValueError
        except ValueError:
            messages.error(request, "Max members must be a valid number between 2 and 100.")
            return redirect("create_group")
            
        try:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    # 1. Verify seller owns this listing
                    cursor.execute("SELECT 1 FROM Listings WHERE listing_id = %s AND seller_id = %s", [listing_id, seller_id])
                    if not cursor.fetchone():
                        messages.error(request, "Invalid listing selected.")
                        return redirect("create_group")
                        
                    # 2. Insert group
                    cursor.execute(
                        """INSERT INTO SharedGroups (listing_id, owner_id, group_name, max_members) 
                           VALUES (%s, %s, %s, %s)""",
                        [listing_id, seller_id, group_name, max_members]
                    )
                    
                    # 3. Get the new group_id
                    cursor.execute("SELECT LAST_INSERT_ID()")
                    new_group_id = cursor.fetchone()[0]
                    
                    # 4. Insert owner into GroupMembers
                    cursor.execute(
                        "INSERT INTO GroupMembers (group_id, user_id) VALUES (%s, %s)",
                        [new_group_id, seller_id]
                    )
                    
            messages.success(request, f"Group '{group_name}' created successfully!")
            return redirect("groups_list")
            
        except Exception as e:
            messages.error(request, "An error occurred while creating the group.")
            return redirect("create_group")

    # GET request
    listings = fetch_all(SELECT_SELLER_LISTINGS, [seller_id])
    return render(request, "marketplace/group_create.html", {"listings": listings})


@role_required_raw("buyer")
@require_POST
def join_group(request, group_id):
    """Safely join a group using row-level locking."""
    buyer_id = request.session["user_id"]
    
    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                # 1. Lock the SharedGroups row
                cursor.execute(
                    "SELECT listing_id, max_members FROM SharedGroups WHERE group_id = %s FOR UPDATE", 
                    [group_id]
                )
                group = cursor.fetchone()
                if not group:
                    messages.error(request, "Group not found.")
                    return redirect("groups_list")
                    
                listing_id, max_members = group
                
                # 2. Verify eligibility (Has an Approved order)
                cursor.execute(
                    "SELECT 1 FROM Orders WHERE buyer_id = %s AND listing_id = %s AND order_status = 'Approved' LIMIT 1",
                    [buyer_id, listing_id]
                )
                if not cursor.fetchone():
                    messages.error(request, "You must have an approved order for this subscription to join its group.")
                    return redirect("groups_list")
                
                # 3. Check capacity safely under lock
                cursor.execute("SELECT COUNT(*) FROM GroupMembers WHERE group_id = %s", [group_id])
                current_members = cursor.fetchone()[0]
                
                if current_members >= max_members:
                    messages.error(request, "Sorry, this group is already full.")
                    return redirect("groups_list")
                
                # 4. Insert (gracefully handle if already a member via composite PK)
                try:
                    cursor.execute(
                        "INSERT INTO GroupMembers (group_id, user_id) VALUES (%s, %s)",
                        [group_id, buyer_id]
                    )
                    messages.success(request, "You have successfully joined the group!")
                except IntegrityError:
                    messages.info(request, "You are already a member of this group.")
                    
    except Exception as e:
        messages.error(request, "An unexpected error occurred while joining the group.")
        
    return redirect("groups_list")


@role_required_raw("buyer")
@require_POST
def leave_group(request, group_id):
    """Leave a shared group."""
    buyer_id = request.session["user_id"]
    
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM GroupMembers WHERE group_id = %s AND user_id = %s",
                [group_id, buyer_id]
            )
            # If affected_rows > 0 we can show success
            if cursor.rowcount > 0:
                messages.success(request, "You have left the group.")
            else:
                messages.error(request, "You are not a member of this group.")
    except Exception:
        messages.error(request, "Could not leave the group. Please try again.")
        
    return redirect("groups_list")
