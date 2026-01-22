from django.core.paginator import Paginator
from django.db.models import Count


def annotate_comment(queryset):
    return queryset.annotate(comment_count=Count('comments'))


def paginate_queryset(request, queryset, per_page=10):
    paginator = Paginator(queryset, per_page)
    page_number = request.GET.get('page')
    return paginator.get_page(page_number)
