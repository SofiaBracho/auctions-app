from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("categories/<str:category>/", views.categories, name="categories"),
    path("new", views.new, name="new"),
    path("watchlist", views.watchlist, name="watchlist"),
    path("listings/<str:id>", views.listings, name="listings"),
    path("login", views.login_view, name="login"),
    path("logout", views.logout_view, name="logout"),
    path("register", views.register, name="register")
]
