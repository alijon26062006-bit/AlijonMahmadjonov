from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("destinations/", views.destinations_view, name="destinations"),
    path("destinations/<slug:slug>/", views.destination_detail, name="destination_detail"),
    path("cart/", views.cart_view, name="cart"),
    path("checkout/", views.checkout_view, name="checkout"),
    path("order/<str:public_id>/", views.order_status, name="order_status"),
]
