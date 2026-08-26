"""URL routes for the marketplace app."""

from django.urls import path

from . import views_auth, views_browse, views_coupons, views_home, views_wishlist

urlpatterns = [
    # Landing page
    path("", views_home.landing, name="home"),
    # Catalogue
    path("browse/", views_browse.browse, name="browse"),
    path("listing/<int:listing_id>/", views_browse.listing_detail, name="listing_detail"),
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
