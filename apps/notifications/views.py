from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Notification


@login_required
def inbox(request):
    page = Paginator(Notification.objects.filter(user=request.user), 25).get_page(request.GET.get("page"))
    return render(request, "notifications/inbox.html", {"page_obj": page})


@login_required
@require_POST
def mark_read(request, pk):
    notice = get_object_or_404(Notification, pk=pk, user=request.user)
    if notice.read_at is None:
        notice.read_at = timezone.now()
        notice.save(update_fields=["read_at"])
    return redirect("notifications:inbox")
