from django.shortcuts import render

# Create your views here.






def about_page(request):
    return render(request, "estate/about.html")



def properties_page(request):
    """_summary_

    Args:
        request (_type_): _description_
    """
    return render(request, "estate/properties.html")







def agents(request):
    """Display all verified agents"""
    from agents.models import Agent
    from django.core.paginator import Paginator
    
    # Get all verified agents
    agents_list = Agent.objects.filter(
        is_active=True,
        verification_status='verified'
    ).select_related('user').order_by('-created')
    
    # Pagination
    paginator = Paginator(agents_list, 12)  # 12 agents per page
    page_number = request.GET.get('page')
    agents = paginator.get_page(page_number)
    
    # Get featured agent (first verified agent or None)
    featured_agent = agents_list.first() if agents_list.exists() else None
    
    context = {
        'agents': agents,
        'featured_agent': featured_agent,
        'total_agents': agents_list.count(),
    }
    
    return render(request, "estate/agents.html", context)


def agents_details(request):
    return render(request, "estate/agent-profile.html")




def service(request):
    return render(request, "estate/services.html")


def service_detail_page(request):
    return render(request, "estate/service-details.html")


def contact(request):
    return render(request, "estate/contact.html")



def properties_details(request):
    return render(request, "estate/property-details.html")



def dashboard_user(request):
    return render(request, "estate/dashboard.html")



def privacy_policy(request):
    return render(request, "estate/privacy.html")