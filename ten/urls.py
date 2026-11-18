from django.urls import path
from game import views, social, spectator
from django.contrib.auth import views as auth
urlpatterns = [path('',views.index),path('room/<str:code>/',views.index),path('api/<str:action>/',views.api)]
urlpatterns += [
    path('login/',views.PlayerLoginView.as_view(),name='login'),
    path('signup/',views.signup,name='signup'),
    path('logout/',auth.LogoutView.as_view(),name='logout'),
    path('profile/',views.profile,name='profile'),
    path('password-reset/',auth.PasswordResetView.as_view(),name='password_reset'),
    path('password-reset/sent/',auth.PasswordResetDoneView.as_view(),name='password_reset_done'),
    path('reset/<uidb64>/<token>/',auth.PasswordResetConfirmView.as_view(),name='password_reset_confirm'),
    path('reset/done/',auth.PasswordResetCompleteView.as_view(),name='password_reset_complete'),
]
from django.conf import settings
from django.conf.urls.static import static
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.BASE_DIR/'static')

urlpatterns += [
    path('friends/',social.home,name='friends'),
    path('social/api/overview/',social.overview),
    path('social/api/conversation/<int:pk>/',social.conversation),
    path('social/api/action/<str:action>/',social.action),
    path('watch/<str:code>/',spectator.watch,name='watch'),
    path('spectate/api/<str:code>/',spectator.state),
]

from django.contrib import admin
urlpatterns += [path('admin/',admin.site.urls)]

# Dutch has its own table, API and allowlisted spectator view.
from game import dutch_views
urlpatterns += [
    path('dutch/',dutch_views.index,name='dutch'),
    path('dutch/room/<str:code>/',dutch_views.index,name='dutch_room'),
    path('dutch/watch/<str:code>/',dutch_views.index,{'watch':True},name='dutch_watch'),
    path('dutch/api/<str:action>/',dutch_views.api),
]
