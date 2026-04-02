from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from .models import Post, Category, Author, Comment
from django.http import JsonResponse
import logging

logger = logging.getLogger(__name__)

def post_lists(request):
    # DEBUG: Check all posts and their statuses
    all_posts = Post.objects.all()
    print(f"Total posts in database: {all_posts.count()}")
    
    for post in all_posts[:5]:  # Print first 5 posts
        print(f"Post: {post.name}, Status: '{post.status}'")
    
    # Get only published posts
    posts_list = Post.objects.filter(status='published').order_by('-publish')
    print(f"Published posts count: {posts_list.count()}")
    
    # If no published posts, show all posts for now (temporary)
    if not posts_list.exists():
        print("No published posts found, showing all posts...")
        posts_list = Post.objects.all().order_by('-publish')
    
    # Pagination - 6 posts per page
    paginator = Paginator(posts_list, 2)
    page = request.GET.get('page', 1)
    
    try:
        posts = paginator.page(page)
    except PageNotAnInteger:
        posts = paginator.page(1)
    except EmptyPage:
        posts = paginator.page(paginator.num_pages)
    
    context = {
        'posts': posts,
        'paginator': paginator
    }
    return render(request, 'estate/blog.html', context)



def post_details(request, slug, year, month, day):
    """
    A method to get an object with its slug
    
    Args:
        request (_type_): _description_
        slug (_type_): _description_
    """
    try:
        comment_post = None
        post = get_object_or_404(Post, slug=slug, publish__year=year, publish__month=month, publish__day=day)
        comment_posts = post.comments.all()
        comment_count = comment_posts.count()
        
        if request.method == "POST":
            comment = request.POST.get("comment", "").strip()
            if not comment:
                return JsonResponse({
                    "status": "error",
                    "message": "You Cannot Submit An Empty Post"
                })
            else:
                pass    
            user = request.user
            comment_post = Comment.objects.create(post=post, user=user, text=comment)
            comment_data = {
                "id": comment_post.id,
                "user": comment_post.user.username,
                "user_image": comment_post.user.get_users_image(),
                "comment": comment_post.text,
                "comment_post": comment_post.post,
            }
            return JsonResponse({
                "status": "success",
                "message": "Comment Created Successfully",
                "comment_data": str(comment_data)
            })
        
        
        return render(request, "estate/blog-details.html", {"post": post, "comment_post": comment_post, "comment_posts": comment_posts, 'comment_count': comment_count})
    
    except Post.DoesNotExist:
        logger.error(f"Blog post not found: slug={slug}, date={year}/{month}/{day}")
        raise
    except Exception as e:
        logger.error(f"Error in post_details view: {str(e)}", exc_info=True)
        raise



