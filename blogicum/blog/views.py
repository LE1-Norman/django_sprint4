from django.shortcuts import get_object_or_404, render, redirect
from blog.models import Post, Category, Comment
from django.utils import timezone
from django.http import Http404

from django.views.generic import (
    DetailView, UpdateView, ListView, CreateView, DeleteView
)

from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin

from django.core.paginator import Paginator
from django.urls import reverse, reverse_lazy

from .forms import PostCreateForm, CommentForm
from django.db.models import Count

User = get_user_model()


class ProfileDetailView(DetailView):
    model = User
    template_name = 'blog/profile.html'
    context_object_name = 'profile'

    def get_object(self, queryset=None):
        return get_object_or_404(User, username=self.kwargs['username'])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        is_owner = (
            self.request.user.is_authenticated
            and self.request.user == self.object
        )

        if is_owner:
            posts = Post.objects.filter(author=self.object)
        else:
            posts = Post.objects.filter(
                author=self.object,
                is_published=True,
                category__is_published=True,
                pub_date__lte=timezone.now()
            )

        posts = posts.annotate(
            comment_count=Count('comments')
        ).select_related('category').order_by('-pub_date')

        paginator = Paginator(posts, 10)
        page_number = self.request.GET.get('page')
        context['page_obj'] = paginator.get_page(page_number)
        return context


class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    model = User
    fields = ['first_name', 'last_name', 'username', 'email']
    template_name = 'blog/user.html'

    def get_object(self, queryset=None):
        return self.request.user

    def get_success_url(self):
        return reverse(
            'blog:profile',
            kwargs={'username': self.request.user.username}
        )


class IndexListView(ListView):
    model = Post
    template_name = 'blog/index.html'
    paginate_by = 10
    ordering = ['-pub_date']

    def get_queryset(self):
        return Post.objects.filter(
            is_published=True,
            category__is_published=True,
            pub_date__lte=timezone.now()
        ).select_related(
            'category',
            'author',
            'location'
        ).annotate(
            comment_count=Count('comments')
        ).order_by('-pub_date')


# def sort_post_by_date():
#     current_time = timezone.now()
#     return Post.objects.filter(
#         is_published=True,
#         pub_date__lte=current_time,
#         category__is_published=True
#     )


def post_detail(request, post_id):
    template = 'blog/detail.html'

    try:
        post = Post.objects.get(id=post_id)
    except Post.DoesNotExist:
        raise Http404(f"Пост с ID {post_id} не найден.")

    is_author = request.user.is_authenticated and post.author == request.user
    is_visible = (
        post.is_published
        and post.category.is_published
        and post.pub_date <= timezone.now()
    )

    if not (is_author or is_visible):
        raise Http404(f"Пост с ID {post_id} недоступен.")

    comment_form = CommentForm()
    comments = post.comments.all()
    context = {
        'post': post,
        'form': comment_form,
        'comments': comments,
    }
    return render(request, template, context)


def category_posts(request, category_slug):
    template = 'blog/category.html'
    category = get_object_or_404(
        Category.objects.filter(is_published=True),
        slug=category_slug
    )

    post_list = category.posts_by_category.filter(
        is_published=True,
        pub_date__lte=timezone.now()
    ).annotate(
        comment_count=Count('comments')
    ).select_related(
        'author',
        'location'
    ).order_by('-pub_date')

    paginator = Paginator(post_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'category': category,
        'page_obj': page_obj
    }
    return render(request, template, context)


class PostCreateView(LoginRequiredMixin, CreateView):
    model = Post
    form_class = PostCreateForm
    template_name = 'blog/create.html'

    def form_valid(self, form):
        form.instance.author = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse(
            'blog:profile',
            kwargs={'username': self.request.user.username}
        )


class PostUpdateView(UpdateView):
    model = Post
    form_class = PostCreateForm
    template_name = 'blog/create.html'
    pk_url_kwarg = 'post_id'

    def dispatch(self, request, *args, **kwargs):
        post = self.get_object()

        if post.author != request.user or not request.user.is_authenticated:
            return redirect('blog:post_detail', post_id=post.id)
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse(
            'blog:post_detail',
            kwargs={'post_id': self.object.id}
        )


class CommentCreateView(LoginRequiredMixin, CreateView):
    model = Comment
    form_class = CommentForm
    template_name = 'blog/detail.html'

    def dispatch(self, request, *args, **kwargs):
        self.this_post = get_object_or_404(Post, id=self.kwargs['post_id'])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.author = self.request.user
        form.instance.post = self.this_post
        return super().form_valid(form)

    def get_success_url(self):
        return reverse(
            'blog:post_detail',
            kwargs={'post_id': self.object.post.id}
        )


class CommentUpdateView(LoginRequiredMixin, UpdateView):
    model = Comment
    pk_url_kwarg = 'comment_id'
    form_class = CommentForm
    template_name = 'blog/comment.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['comment'] = self.object
        context['post_id'] = self.object.post.id
        return context

    def dispatch(self, request, *args, **kwargs):
        comment = self.get_object()

        if comment.author != request.user or not request.user.is_authenticated:
            return redirect('blog:post_detail', post_id=comment.post.id)
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse(
            'blog:post_detail',
            kwargs={'post_id': self.object.post.id}
        )


class PostDeleteView(LoginRequiredMixin, DeleteView):
    model = Post
    pk_url_kwarg = 'post_id'
    template_name = 'blog/create.html'

    def get_queryset(self):
        return Post.objects.filter(author=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = PostCreateForm(instance=self.object)
        return context

    def get_success_url(self):
        return reverse_lazy('blog:index')


class CommentDeleteView(LoginRequiredMixin, DeleteView):
    model = Comment
    pk_url_kwarg = 'comment_id'
    template_name = 'blog/comment.html'

    def get_queryset(self):
        return Comment.objects.filter(author=self.request.user)

    def get_success_url(self):
        return reverse_lazy(
            'blog:post_detail',
            kwargs={'post_id': self.object.post.id}
        )
