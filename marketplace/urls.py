"""URL routes for the marketplace app."""

from django.urls import path

from .views import auth, browse, coupons, home, orders, reviews, wishlist

urlpatterns = [
    # Landing page
    path("", home.landing, name="home"),
    # Catalogue
    path("browse/", browse.browse, name="browse"),
    path("listing/<int:listing_id>/", browse.listing_detail, name="listing_detail"),
    path("listing/<int:listing_id>/checkout/", orders.checkout, name="checkout"),
    path("orders/<int:order_id>/confirmation/", orders.order_confirmation, name="order_confirmation"),
    path("orders/", orders.buyer_orders, name="buyer_orders"),
    path("orders/<int:order_id>/payment/", orders.submit_payment, name="submit_payment"),
    path("admin/orders/", orders.admin_orders, name="admin_orders"),
    path("admin/orders/<int:order_id>/review/", orders.review_order, name="review_order"),
    path("listing/<int:listing_id>/review/", reviews.create_review, name="create_review"),
    # Authentication
    path("register/", auth.register, name="register"),
    path("login/", auth.login_view, name="login"),
    path("logout/", auth.logout_view, name="logout"),
    # Wishlist
    path("wishlist/", wishlist.wishlist, name="wishlist"),
    path("wishlist/add/<int:listing_id>/", wishlist.wishlist_add, name="wishlist_add"),
    path(
        "wishlist/remove/<int:listing_id>/",
        wishlist.wishlist_remove,
        name="wishlist_remove",
    ),
    # Coupons
    path("coupons/validate/", coupons.validate_coupon_api, name="validate_coupon"),
]
