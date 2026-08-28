"""URL routes for the marketplace app."""

from django.urls import path

from . import (
    views_auth,
    views_browse,
    views_coupons,
    views_home,
    views_orders,
    views_reviews,
    views_wishlist,
)

urlpatterns = [
    # Landing page
    path("", views_home.landing, name="home"),
    # Catalogue
    path("browse/", views_browse.browse, name="browse"),
    path("listing/<int:listing_id>/", views_browse.listing_detail, name="listing_detail"),
    path("listing/<int:listing_id>/checkout/", views_orders.checkout, name="checkout"),
    path("orders/<int:order_id>/confirmation/", views_orders.order_confirmation, name="order_confirmation"),
    path("orders/", views_orders.buyer_orders, name="buyer_orders"),
    path("orders/<int:order_id>/payment/", views_orders.submit_payment, name="submit_payment"),
    path("admin/orders/", views_orders.admin_orders, name="admin_orders"),
    path("admin/orders/<int:order_id>/review/", views_orders.review_order, name="review_order"),
    path("listing/<int:listing_id>/review/", views_reviews.create_review, name="create_review"),
    # Authentication
    path("register/", views_auth.register, name="register"),
    path("login/", views_auth.login_view, name="login"),
    path("logout/", views_auth.logout_view, name="logout"),
    # Wishlist
    path("wishlist/", views_wishlist.wishlist, name="wishlist"),
    path("wishlist/add/<int:listing_id>/", views_wishlist.wishlist_add, name="wishlist_add"),
    path(
        "wishlist/remove/<int:listing_id>/",
        views_wishlist.wishlist_remove,
        name="wishlist_remove",
    ),
    # Coupons
    path("coupons/validate/", views_coupons.validate_coupon_api, name="validate_coupon"),
]
